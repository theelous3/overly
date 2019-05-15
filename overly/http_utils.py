__all__ = [
    "get_content_type",
    "extract_query",
    "extract_form_urlencoded",
    "create_content_len_header",
    "extract_cookies",
    "cookies_to_key_value",
    "cookiest_to_output"
]

from http.cookies import SimpleCookie

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
    headers = [
        [header.decode(), value.decode()]
        for header, value in client_headers
    ]

    try:
        cookies = next(v for k, v in headers if k == 'cookie')
    except StopIteration:
        return None

    cookies = [c for c in cookies.split(";") if c]
    cookies = [cookie.split("=") for cookie in cookies]
    cookies = [[k.strip(), v.strip()] for k, v in cookies]
    cookies = [f'{k}="{v}"' if " " in v else f"{k}={v}" for k, v in cookies]

    joined_cookies = ";".join(cookies)
    return SimpleCookie(joined_cookies)


def cookies_to_key_value(cookies: SimpleCookie) -> [[str, str]]:
    return [f"{cookie_name}={cookies[cookie_name].coded_value}" for cookie_name in cookies]

def cookiest_to_output(cookies: SimpleCookie) -> str:
    cookies = cookies_to_key_value(cookies)
    return "; ".join(cookies)


def create_content_len_header(body: bytes) -> (str, str):
    if hasattr(body, "encode"):
        raise TypeError("content-length must be calculated from bytes-like object")
    return ("content-length", str(len(body)).encode())
