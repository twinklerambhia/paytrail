from rest_framework import serializers


class AgentMessageRequestSerializer(serializers.Serializer):
    """Validates the new merchant message; passes the transcript through intact.

    `conversation` is the prior transcript this backend itself produced, echoed
    back by the client each turn (the agent is stateless per request). It is
    deliberately NOT validated field-by-field: provider message shapes vary
    (`content: null` on tool-call messages, `tool_calls: null` on plain
    replies, provider-specific extras), and a strict schema rejects valid
    transcripts without buying safety — a hostile client could forge roles
    either way.

    Note: because the transcript is client-held, a malicious caller could
    forge a tool result. Acceptable for a synthetic-data prototype; a real
    deployment would keep the transcript server-side keyed by session, and
    the tool-execution audit log (ToolExecution) is the authoritative record
    of what actually ran regardless.
    """

    message = serializers.CharField()
    conversation = serializers.ListField(
        child=serializers.DictField(), required=False, default=list
    )
