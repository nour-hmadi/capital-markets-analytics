"""The AI assistant, tested with a fake model: no internet, no API key, the same answers every time."""
from langchain_core.messages import SystemMessage

from assistant import INSTRUCTIONS, build_agent, reply


def test_the_assistant_answers(fake_model):
    agent = build_agent(model=fake_model("A bond is a loan to a government or a company."))
    assert reply(agent, [{"role": "user", "content": "What is a bond?"}]).startswith("A bond is a loan")


def test_the_whole_conversation_is_sent_every_time(fake_model):
    """The model has no memory: the app sends the instructions, then the whole conversation, each time."""
    model = fake_model("It's the fixed interest the bond pays every year.")
    conversation = [
        {"role": "user", "content": "What is a bond?"},
        {"role": "assistant", "content": "A bond is a loan."},
        {"role": "user", "content": "And its coupon?"},
    ]
    reply(build_agent(model=model), conversation)
    sent = model.received[0]
    assert isinstance(sent[0], SystemMessage) and sent[0].content == INSTRUCTIONS
    assert [message.content for message in sent[1:]] == [message["content"] for message in conversation]
