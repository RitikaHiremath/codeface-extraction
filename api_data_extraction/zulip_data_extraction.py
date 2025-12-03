import zulip
import json
import time

# ZULIP_CONFIG_FILE = "/Users/ritikahiremath/Downloads/zuliprc.txt"
ZULIP_CONFIG_FILE = "zuliprc.txt"
client = zulip.Client(config_file=ZULIP_CONFIG_FILE)


def safe_get_topics(stream_id):
    """
    Fetches all the topics from Zulip rust.

    :params: stream_id : id of the stream.
    :return: list of topics in the stream. If no topics exist then returns empty list.

    """
    while True:
        resp = client.get_stream_topics(stream_id=stream_id)
        if resp["result"] == "success":
            return [t["name"] for t in resp["topics"]]
        elif resp["result"] == "error" and resp.get("code") == "RATE_LIMIT_HIT":
            retry = int(resp.get("retry_after", 5))
            print(f"Rate limit hit, retrying in {retry}s...")
            time.sleep(retry)
        else:
            print("Error fetching topics:", resp)
            return []


def topics_extraction():
    """
    Fetches Extract all streams and topics 

    :return: returns a dictory of topics in the stream.
    """
    streams = client.get_streams()["streams"]
    data = {}

    for i, s in enumerate(streams, 1):
        stream_name = s["name"]
        print(f"[{i}/{len(streams)}] Getting topics for: {stream_name}")

        topics = safe_get_topics(s["stream_id"])
        data[stream_name] = {
            "topics": topics
        }

        time.sleep(0.5)

    with open("zulip_streams_and_topics.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("Saved zulip_streams_and_topics.json")
    return data

     
def load_stream_topics(file_path):
    """
    Fetches all the streams and topics from the file. 

    :params: file_path : path of the file for streams and topics.
    :return: returns the content of the file.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
    


def fetch_all_messages_for_stream(stream_name,topic_name):
    """
    Fetches all the messages in a topic through API call. 

    :params: topic_name : name of the topic for which all. the messages should be fetched.
    :return: returns all the messages from that topic.
    """
    
    all_messages = []
    anchor = 0  # Start from oldest

    while True:
        request = {
            "anchor": anchor,
            "num_before": 0,
            "num_after": 500,       # max allowed
            "narrow": [
                {"operator": "stream", "operand": stream_name},
                {"operator": "topic", "operand": topic_name}
            ]
        }

        resp = client.get_messages(request)
        msgs = resp["messages"]

        if not msgs:
            break

        all_messages.extend(msgs)

        # Move anchor forward for next batch
        anchor = msgs[-1]["id"] + 1

        time.sleep(0.4)

    return all_messages

def discussion_id_update(msgs):
    # Sort by timestamp ascending
    msgs = sorted(msgs, key=lambda m: m["timestamp"])

    for idx, m in enumerate(msgs, start=1):
        m["stream_id"] = f'{m["stream_id"]}#{idx}'

    return msgs


def messages_extraction_for_each_stream(streams_with_topics):
    final_output = []

    for stream_name, info in streams_with_topics.items():
        topics = info["topics"]
        # go topic wise here. fetch all messages for a topic
        for topic in topics:
            print(f"\n Fetching all messages for stream: {stream_name} and topic: {topic}")
             
            msgs = fetch_all_messages_for_stream(stream_name,topic)
            
            msgs = discussion_id_update(msgs)

            for m in msgs:
                final_output.append({
                    "discussion_id": m["stream_id"],
                    "discusssion_topic": m["subject"],
                    "sender_full_name": m["sender_full_name"],
                    "sender_email": m["sender_email"],
                    "stream": stream_name,
                    "content": m["content"],
                    "timestamp": m["timestamp"]
            })

    # Save everything
    output_file = "issues.json"
    with open(output_file, "w") as f:
        json.dump(final_output, f, indent=2)

    print(f"\n Saved ALL stream messages to: {output_file}")

if __name__ == "__main__":
    streams_and_topics = load_stream_topics("zulip_streams_and_topics.json")
    messages_extraction_for_each_stream(streams_and_topics)
