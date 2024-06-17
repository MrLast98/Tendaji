from torch import no_grad, FloatTensor, softmax
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from datetime import datetime
tokenizer = AutoTokenizer.from_pretrained("DT12the/distilbert-sentiment-analysis")
model = AutoModelForSequenceClassification.from_pretrained("DT12the/distilbert-sentiment-analysis")
# THIS SUCKS IN ITALIAN


def toxicity_analysis(message):
    tokenized_message = tokenizer(message, truncation=True, max_length=512, padding='max_length', return_tensors="pt")
    input_ids = tokenized_message['input_ids']
    attention_mask = tokenized_message['attention_mask'].type(FloatTensor)

    with no_grad():
        outputs = model(input_ids=input_ids, attention_mask=attention_mask)
    probabilities = softmax(outputs.logits, dim=1)
    probabilities = probabilities.numpy()

    positive_percentage = probabilities[0, 0] * 100
    negative_percentage = probabilities[0, 1] * 100

    return ("🟢 Positive " + str("{:.2f}%".format(positive_percentage))) if positive_percentage > negative_percentage else (
            "🔴 Negative " + str("{:.2f}%".format(negative_percentage)))


async def analyse_and_print(self, message):
    analysis = toxicity_analysis(message['parameters'].strip('\r\n'))
    trimmed_analisys = analysis[:-7]
    positive = True if "Positive" in analysis else False
    confidence = float(analysis[-7:-1].strip())
    # TODO: Filtering for bots for the example channel - DELETE
    if message['tags']['display-name'] not in ['StreamDjBot', 'TheBriskBot']:
        insert_message(self, message['parameters'].strip('\r\n'), trimmed_analisys, message['tags']['display-name'], positive, confidence)
    self.manager.print.print_to_logs(
        f"{message['tags']['display-name']}, {message['parameters'].strip('\r\n')} | {analysis}",
        self.manager.print.BLUE)


def insert_message(self, message, sentiment, username, positive, confidence):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Format current timestamp

    # Insert the new message with created_at and updated_at fields
    self.cursor.execute("""
        INSERT INTO messages (message, sentiment, username, positive, confidence, created_at, updated_at) 
        VALUES (?,?,?,?,?,?,?)
    """, (message, sentiment, username, positive, confidence, now, now))

    # Commit changes
    self.conn.commit()

