__all__ = [
    "get_content_type",
    "extract_query",
    "extract_form_urlencoded",
    "create_content_len_header"
]


from .errors import EndSteps


def get_content_type(headers: [(str, str)]) -> str:
    return next((v for k, v in headers if k == b'content-type'), None)



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


def create_content_len_header(body: bytes) -> (str, str):
    if hasattr(body, "encode"):
        raise TypeError("content-length must be calculated from bytes-like object")
    return ("content-length", str(len(body)).encode())
