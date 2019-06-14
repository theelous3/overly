__all__ = [
    "get_content_type",
    "extract_query",
    "extract_form_urlencoded",
    "create_content_len_header",
    "extract_cookies",
    "cookies_to_headers",
    "cookies_to_output",
    "parse_multipart",
    "extract_multipart_form_file",
    "extract_multipart_form_data",
    "extract_multipart_json",
]

from io import BytesIO
from json import loads
from http.cookies import SimpleCookie

from sansio_multipart import MultipartParser, Part, PartData, Events

from .errors import EndSteps


def get_content_type(headers: [(str, str)]) -> str:
    return next((v for k, v in headers if k == b"content-type"), None)


def extract_query(query: str) -> [(str, str)]:
    query_list = []
    for pair in query.split("&"):
        k, v = pair.split("=", 1)
        query_list.append((k, v))

    return query_list


def extract_form_urlencoded(body: str) -> [(str, str)]:
    form_list = []

    body = body.split("\n")

    for line in body:
        k, v = line.split("=", 1)
        form_list.append((k, v))

    return form_list


def extract_cookies(client_headers):
    headers = [[header.decode(), value.decode()] for header, value in client_headers]

    try:
        cookies = next(v for k, v in headers if k == "cookie")
    except StopIteration:
        return None

    cookies = [c for c in cookies.split(";") if c]
    cookies = [cookie.split("=") for cookie in cookies]
    cookies = [[k.strip(), v.strip()] for k, v in cookies]
    cookies = [f'{k}="{v}"' if " " in v else f"{k}={v}" for k, v in cookies]

    joined_cookies = ";".join(cookies)
    return SimpleCookie(joined_cookies)


def cookies_to_output(cookies: SimpleCookie) -> [[str, str]]:
    return [
        f"{cookie_name}={cookies[cookie_name].coded_value}" for cookie_name in cookies
    ]


def cookies_to_headers(cookies: SimpleCookie) -> [(str, str)]:
    return [("set-cookie", cookie) for cookie in cookies_to_output(cookies)]


def create_content_len_header(body: bytes) -> (str, str):
    if hasattr(body, "encode"):
        raise TypeError("content-length must be calculated from bytes-like object")
    return ("content-length", str(len(body)).encode())


def parse_multipart(content_type: bytes, body: bytes) -> [Part]:

    content_type, boundary = content_type.split(b";")
    boundary = boundary.lstrip()
    _, boundary = boundary.split(b"=")

    with MultipartParser(boundary) as parser:
        parts = []
        current_part = None

        events = parser.parse(body)

        for event in events:
            if isinstance(event, Part):
                if current_part is not None:
                    parts.append(current_part)
                current_part = event
            elif isinstance(event, PartData):
                if current_part is not None:
                    current_part.buffer(event)
            elif event is Events.FINISHED:
                parts.append(current_part)

    return parts


def extract_multipart_form_file(part: Part) -> dict:
    file_data = {
        "name": part.name,
        "filename": part.filename,
        "content-type": part.content_type,
        "charset": part.charset,
        "content-length": part.size,
        "file": part.value,
    }

    return file_data


def extract_multipart_form_data(part: Part) -> dict:
    form_data = {
        "name": part.name,
        "content-type": part.content_type,
        "charset": part.charset,
        "content-length": part.size,
        "form_data": part.value,
    }

    return form_data


def extract_multipart_json(part: Part) -> dict:
    json = {
        "name": part.name,
        "content-type": part.content_type,
        "charset": part.charset,
        "content-length": part.size,
        "json": loads(part.value),
    }

    return json
