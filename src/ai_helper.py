from torch import FloatTensor, no_grad
from torch.nn.functional import softmax
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODELS_SETUP = [
    {
        "name": "philschmid/distilbert-base-multilingual-cased-sentiment-2",
        "tokenizer": AutoTokenizer.from_pretrained("philschmid/distilbert-base-multilingual-cased-sentiment-2"),
        "model": AutoModelForSequenceClassification.from_pretrained(
            "philschmid/distilbert-base-multilingual-cased-sentiment-2")
    },
    {
        "name": "citizenlab/distilbert-base-multilingual-cased-toxicity",
        "tokenizer": AutoTokenizer.from_pretrained("citizenlab/distilbert-base-multilingual-cased-toxicity"),
        "model": AutoModelForSequenceClassification.from_pretrained(
            "citizenlab/distilbert-base-multilingual-cased-toxicity")
    }
]


def analyze_sentiment(email):
    sentiments = []
    for mod in MODELS_SETUP:
        match mod["name"]:
            case "philschmid/distilbert-base-multilingual-cased-sentiment-2":
                sentiments.append(("Distilbert2", distilbert_multi_analysis(mod, email)))
            case "citizenlab/distilbert-base-multilingual-cased-toxicity":
                sentiments.append(("ToxicityLevel", distilbert_analysis(mod, email)))
    return prettify_output(sentiments)


def prettify_output(sentiments):
    text = ["Sentiment Analysis:"]
    for name, sentiment in sentiments:
        text.append(name + ": " + sentiment)

    text = f"\n".join(text)
    return text


def distilbert_analysis(mod, email):
    tokenizer = mod["tokenizer"]
    model = mod["model"]

    tokenized_email = tokenizer(email, truncation=True, max_length=512, padding='max_length', return_tensors="pt")
    input_ids = tokenized_email['input_ids']
    attention_mask = tokenized_email['attention_mask'].type(FloatTensor)

    with no_grad():
        outputs = model(input_ids=input_ids, attention_mask=attention_mask)
    probabilities = softmax(outputs.logits, dim=1)
    probabilities = probabilities.numpy()

    positive_percentage = probabilities[0, 1] * 100
    negative_percentage = probabilities[0, 0] * 100

    return ("🟢 " + str("{:.2f}%".format(positive_percentage))) if positive_percentage > negative_percentage else (
            "🔴 " + str("{:.2f}%".format(negative_percentage)))


def distilbert_multi_analysis(mod, email):
    tokenizer = mod["tokenizer"]
    model = mod["model"]

    labels = ['Negative', 'Neutral', 'Positive']  # Define the labels

    tokenized_email = tokenizer(email, truncation=True, max_length=512, padding='max_length', return_tensors="pt")
    input_ids = tokenized_email['input_ids']
    attention_mask = tokenized_email['attention_mask'].type(FloatTensor)

    with no_grad():
        outputs = model(input_ids=input_ids, attention_mask=attention_mask)
    probabilities = softmax(outputs.logits, dim=1)
    probabilities = probabilities.numpy()

    percentages = ['{:.2f}%'.format(p * 100) for p in probabilities[0]]
    sentiment_pairs = list(zip(labels, percentages))
    sentiment_pairs.sort(key=lambda x: float(x[1].strip('%')), reverse=True)
    max_value = max(sentiment_pairs, key=percentage_to_float)

    result = ""
    if max_value[0] == "Positive":
        result += f"🟢 {max_value[1]}"
    elif max_value[0] == "Neutral":
        result += f"🔵 {max_value[1]}"
    elif max_value[0] == "Negative":
        result += f"🔴 {max_value[1]}"

    return result


def percentage_to_float(t):
    return float(t[1].strip('%'))
