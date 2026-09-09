from app.itinerary_formatting import format_itinerary


def test_currency_is_literal_and_formatting_and_sources_survive():
    text = "## יום 1\nתקציב $500 לשלושה ימים, כ-$75.9 ליום.\n**בוקר:** טיול\nhttps://en.wikivoyage.org/wiki/Porto"
    result = format_itinerary(text)
    assert result == text.replace("$", "\\$")
    assert format_itinerary(result) == result


def test_already_escaped_currency_is_not_double_escaped():
    assert format_itinerary(r"מחיר \$50") == r"מחיר \$50"
