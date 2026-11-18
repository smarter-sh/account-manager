"""Django Rest Framework YAML parser."""

import yaml
from rest_framework.exceptions import ParseError
from rest_framework.parsers import BaseParser


class YAMLParser(BaseParser):
    """A custom parser for YAML request payloads."""

    media_type = "application/x-yaml"

    def parse(self, stream, media_type=None, parser_context=None):
        """
        Parse a YAML request body.

        :param stream: The request body stream.
        :param media_type: The request's media type.
        :param parser_context: DRF's parser context.
        :returns: The parsed data.
        :raises ParseError: If the body isn't valid UTF-8 YAML, so that DRF answers 400.
        """
        try:
            data = stream.read().decode("utf-8")
            return yaml.safe_load(data)
        except (ValueError, yaml.YAMLError) as exc:
            raise ParseError(f"YAML parse error - {str(exc)}") from exc
