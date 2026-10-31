from rest_framework import serializers


class ConversationMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["user", "assistant", "tool", "system"])
    content = serializers.CharField(allow_blank=True, required=False)
    tool_calls = serializers.JSONField(required=False)
    tool_call_id = serializers.CharField(required=False)


class AgentMessageRequestSerializer(serializers.Serializer):
    message = serializers.CharField()
    conversation = ConversationMessageSerializer(many=True, required=False, default=list)
