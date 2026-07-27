from anthropic import AnthropicVertex
import sys

def test_model(model_name):
    print(f"Testing {model_name}...")
    try:
        client = AnthropicVertex(region="us-east5", project_id="prj-infra-c-cloudops-int-98765")
        message = client.messages.create(
            max_tokens=10,
            messages=[
                {
                    "role": "user",
                    "content": "Hello",
                }
            ],
            model=model_name,
        )
        print(f"Success! Model {model_name} works.")
    except Exception as e:
        print(f"Error testing {model_name}: {e}")

if __name__ == "__main__":
    test_model("claude-3-5-sonnet-v2@20241022")
    test_model("claude-3-5-sonnet@20240620")
