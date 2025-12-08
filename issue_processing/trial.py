import json

def discussion_id_update(issue_data):
    """
    """
    # Group timestamps by discussion_topic
    grouped = {}

    for item in issue_data:
        topic = item["discussion_topic"]
        if topic not in grouped:
            grouped[topic] = []
        grouped[topic].append(item)

    # Process each topic group
    for topic, messages in grouped.items():

        # 1. Sort messages by timestamp ASC
        messages.sort(key=lambda m: m["timestamp"])

        # 2. Add sequential discussion_id suffix (#1, #2, #3...)
        for idx, msg in enumerate(messages, start=1):
            msg["discussion_id"] = f'{msg["discussion_id"]}#{idx}'

    return issue_data


with open("/Users/ritikahiremath/Desktop/extraction/issue_processing/_issues/_issues.json", "r") as f:
    issue_data = json.load(f)
discussion_id_update(issue_data)
print(issue_data)