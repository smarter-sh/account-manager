"""
url helper functions
"""

from urllib.parse import urlparse


def clean_url(url: str) -> str:
    """
    Clean the url of any query strings.
    """
    parsed_url = urlparse(url)
    retval = parsed_url._replace(query="").geturl()
    return retval
