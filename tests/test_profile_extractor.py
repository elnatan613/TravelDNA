"""בדיקה ממוקדת להגדרת קריאת Gemini בחילוץ הטקסט החופשי."""

from unittest import mock

from nlp.profile_extractor import extract_adjustments_from_text


def test_text_extraction_disables_unused_automatic_function_calling():
    fake_client = mock.Mock()
    fake_client.models.generate_content.return_value.text = '{"culture": 0.9}'

    with mock.patch("nlp.profile_extractor.genai.Client", return_value=fake_client):
        result = extract_adjustments_from_text("I love museums")

    assert result == {"culture": 0.9}
    config = fake_client.models.generate_content.call_args.kwargs["config"]
    assert config["response_mime_type"] == "application/json"
    assert config["automatic_function_calling"] == {"disable": True}
