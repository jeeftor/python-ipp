"""Models for IPP."""
from dataclasses import dataclass
from typing import List, Optional

from yarl import URL

from .parser import parse_ieee1284_device_id, parse_make_and_model

PRINTER_STATES = {3: "idle", 4: "printing", 5: "stopped"}


@dataclass(frozen=True)
class Info:
    """Object holding information from IPP."""

    name: str
    printer_name: str
    printer_uri_supported: list
    uptime: int
    command_set: Optional[str] = None
    location: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    printer_info: Optional[str] = None
    serial: Optional[str] = None
    uuid: Optional[str] = None
    version: Optional[str] = None
    more_info: Optional[str] = None

    @staticmethod
    def from_dict(data: dict):
        """Return Info object from IPP response."""
        cmd = None
        name = "IPP Printer"
        name_parts = []
        serial = None
        _printer_name = printer_name = data.get("printer-name", "")
        make_model = data.get("printer-make-and-model", "")
        device_id = data.get("printer-device-id", "")
        uri_supported = data.get("printer-uri-supported", [])
        uuid = data.get("printer-uuid")

        if isinstance(uri_supported, List):
            for uri in uri_supported:
                uri_path = URL(uri).path.lstrip("/")
                if uri_path == _printer_name.lstrip("/"):
                    _printer_name = ""
                    break

        make, model = parse_make_and_model(make_model)
        parsed_device_id = parse_ieee1284_device_id(device_id)

        if parsed_device_id.get("MFG") is not None and len(parsed_device_id["MFG"]) > 0:
            make = parsed_device_id["MFG"]
            name_parts.append(make)

        if parsed_device_id.get("MDL") is not None and len(parsed_device_id["MDL"]) > 0:
            model = parsed_device_id["MDL"]
            name_parts.append(model)

        if parsed_device_id.get("CMD") is not None and len(parsed_device_id["CMD"]) > 0:
            cmd = parsed_device_id["CMD"]

        if parsed_device_id.get("SN") is not None and len(parsed_device_id["SN"]) > 0:
            serial = parsed_device_id["SN"]

        if len(make_model) > 0:
            name = make_model
        elif len(name_parts) == 2:
            name = " ".join(name_parts)
        elif len(_printer_name) > 0:
            name = _printer_name

        return Info(
            command_set=cmd,
            location=data.get("printer-location", ""),
            name=name,
            manufacturer=make,
            model=model,
            printer_name=printer_name,
            printer_info=data.get("printer-info", None),
            printer_uri_supported=uri_supported,
            serial=serial,
            uptime=data.get("printer-up-time", 0),
            uuid=uuid[9:] if uuid else None,  # strip urn:uuid: from uuid
            version=data.get("printer-firmware-string-version", None),
            more_info=data.get("printer-more-info", None)

        )


@dataclass(frozen=True)
class Marker:
    """Object holding marker (ink) info from IPP."""

    marker_id: int
    marker_type: str
    name: str
    color: str
    level: int
    low_level: int
    high_level: int


@dataclass(frozen=True)
class Uri:
    """Object holding URI info from IPP."""

    uri: str
    authentication: str
    security: str


@dataclass(frozen=True)
class State:
    """Object holding the IPP printer state."""

    printer_state: str
    reasons: str
    message: str

    @staticmethod
    def from_dict(data):
        """Return State object from IPP response."""
        state = data.get("printer-state", 0)
        reasons = data.get("printer-state-reasons", None)

        if reasons == "none":
            reasons = None

        return State(
            printer_state=PRINTER_STATES.get(state, state),
            reasons=reasons,
            message=data.get("printer-state-message", None),
        )


@dataclass(frozen=True)
class Printer:
    """Object holding the IPP printer information."""

    info: Info
    markers: List[Marker]
    state: State
    uris: List[Uri]

    @staticmethod
    def from_dict(data):
        """Return Printer object from IPP response."""
        return Printer(
            info=Info.from_dict(data),
            markers=Printer.merge_marker_data(data),
            state=State.from_dict(data),
            uris=Printer.merge_uri_data(data),
        )

    @staticmethod
    def merge_marker_data(data):
        """Return Marker data from IPP response."""
        markers = []
        mlen = 0

        marker_colors = []
        marker_levels = []
        marker_types = []
        marker_highs = []
        marker_lows = []

        marker_names = None
        if isinstance(data.get("marker-names"), List):
            marker_names = data["marker-names"]
            mlen = len(marker_names)

            for k in range(mlen):
                marker_colors.append("")
                marker_levels.append(-2)
                marker_types.append("unknown")
                marker_highs.append(100)
                marker_lows.append(0)

        if isinstance(data.get("marker-colors"), List):
            for k, v in enumerate(data["marker-colors"]):
                if k < mlen:
                    marker_colors[k] = v

        if isinstance(data.get("marker-levels"), List):
            for k, v in enumerate(data["marker-levels"]):
                if k < mlen:
                    marker_levels[k] = v

        if isinstance(data.get("marker-high-levels"), List):
            for k, v in enumerate(data["marker-high-levels"]):
                if k < mlen:
                    marker_highs[k] = v

        if isinstance(data.get("marker-low-levels"), List):
            for k, v in enumerate(data["marker-low-levels"]):
                if k < mlen:
                    marker_lows[k] = v

        if isinstance(data.get("marker-types"), List):
            for k, v in enumerate(data["marker-types"]):
                if k < mlen:
                    marker_types[k] = v

        if isinstance(marker_names, List) and mlen > 0:
            markers = [
                Marker(
                    marker_id=marker_id,
                    marker_type=marker_types[marker_id],
                    name=marker_names[marker_id],
                    color=marker_colors[marker_id],
                    level=marker_levels[marker_id],
                    high_level=marker_highs[marker_id],
                    low_level=marker_lows[marker_id],
                )
                for marker_id in range(mlen)
            ]
            markers.sort(key=lambda x: x.name)

        return markers

    @staticmethod
    def merge_uri_data(data):
        """Return URI data from IPP response."""
        uris = []
        ulen = 0

        _uris = []
        auth = []
        security = []

        if isinstance(data.get("printer-uri-supported"), List):
            _uris = data["printer-uri-supported"]
            ulen = len(_uris)

            for k in range(ulen):
                auth.append(None)
                security.append(None)

        if isinstance(data.get("uri-authentication-supported"), List):
            for k, v in enumerate(data["uri-authentication-supported"]):
                if k < ulen:
                    auth[k] = v if v != "none" else None

        if isinstance(data.get("uri-security-supported"), List):
            for k, v in enumerate(data["uri-security-supported"]):
                if k < ulen:
                    security[k] = v if v != "none" else None

        if isinstance(_uris, List) and ulen > 0:
            uris = [
                Uri(
                    uri=_uris[uri_id],
                    authentication=auth[uri_id],
                    security=security[uri_id],
                )
                for uri_id in range(ulen)
            ]

        return uris
