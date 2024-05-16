from torch import no_grad, FloatTensor, softmax
from transformers import AutoTokenizer, AutoModelForSequenceClassification


# THIS SUCKS IN ITALIAN

def toxicity_analysis(message):
    tokenizer = AutoTokenizer.from_pretrained("DT12the/distilbert-sentiment-analysis")
    model = AutoModelForSequenceClassification.from_pretrained("DT12the/distilbert-sentiment-analysis")
    
    tokenized_message = tokenizer(message, truncation=True, max_length=512, padding='max_length', return_tensors="pt")
    input_ids = tokenized_message['input_ids']
    attention_mask = tokenized_message['attention_mask'].type(FloatTensor)

    with no_grad():
        outputs = model(input_ids=input_ids, attention_mask=attention_mask)
    probabilities = softmax(outputs.logits, dim=1)
    probabilities = probabilities.numpy()

    positive_percentage = probabilities[0, 0] * 100
    negative_percentage = probabilities[0, 1] * 100

    return ("🟢 " + str("{:.2f}%".format(positive_percentage))) if positive_percentage > negative_percentage else (
            "🔴 " + str("{:.2f}%".format(negative_percentage)))
