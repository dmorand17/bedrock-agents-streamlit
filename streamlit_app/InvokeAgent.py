import base64
import io
import json
import logging
import os
import sys

import boto3
from boto3.session import Session
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
from botocore.exceptions import ClientError
from requests import request

logging.basicConfig(format="%(levelname)s %(asctime)s %(message)s", level=logging.INFO)
logger = logging.getLogger()


# For this to run on a local machine in VScode, you need to set the AWS_PROFILE environment variable to the name of the profile/credentials you want to use.

# check for credentials
# echo $AWS_ACCESS_KEY_ID
# echo $AWS_SECRET_ACCESS_KEY
# echo $AWS_SESSION_TOKEN

agentId = "IP6TTVP5AP"  # INPUT YOUR AGENT ID HERE
agentAliasId = (
    "IMBBRAE6VG"  # Hits draft alias, set to a specific alias id for a deployed version
)
theRegion = "us-west-2"

os.environ["AWS_REGION"] = theRegion
region = os.environ.get("AWS_REGION")
llm_response = ""
bedrock_agent_runtime = boto3.client("bedrock-agent-runtime")


def sigv4_request(
    url,
    method="GET",
    body=None,
    params=None,
    headers=None,
    service="execute-api",
    region=os.environ["AWS_REGION"],
    credentials=Session().get_credentials().get_frozen_credentials(),
):
    """Sends an HTTP request signed with SigV4
    Args:
    url: The request URL (e.g. 'https://www.example.com').
    method: The request method (e.g. 'GET', 'POST', 'PUT', 'DELETE'). Defaults to 'GET'.
    body: The request body (e.g. json.dumps({ 'foo': 'bar' })). Defaults to None.
    params: The request query params (e.g. { 'foo': 'bar' }). Defaults to None.
    headers: The request headers (e.g. { 'content-type': 'application/json' }). Defaults to None.
    service: The AWS service name. Defaults to 'execute-api'.
    region: The AWS region id. Defaults to the env var 'AWS_REGION'.
    credentials: The AWS credentials. Defaults to the current boto3 session's credentials.
    Returns:
     The HTTP response
    """

    # sign request
    req = AWSRequest(method=method, url=url, data=body, params=params, headers=headers)
    SigV4Auth(credentials, service, region).add_auth(req)
    req = req.prepare()

    # send request
    return request(method=req.method, url=req.url, headers=req.headers, data=req.body)


def askQuestion(question, url, endSession=False):
    myobj = {"inputText": question, "enableTrace": True, "endSession": endSession}
    print(f"myobj: {myobj}")

    # send request
    response = sigv4_request(
        url,
        method="POST",
        service="bedrock",
        headers={
            "content-type": "application/json",
            "accept": "application/json",
        },
        region=theRegion,
        body=json.dumps(myobj),
    )
    print(f"{response=}")
    print(dump.dump_all(response).decode("utf-8"))
    return decode_response(response)


def askQuestion2(question, sessionId, endSession=False):
    myobj = {"inputText": question, "enableTrace": True, "endSession": endSession}

    try:
        response = bedrock_agent_runtime.invoke_agent(
            agentAliasId=agentAliasId,
            agentId=agentId,
            enableTrace=True,
            sessionId=sessionId,
            inputText=question,
        )

        completion = ""
        trace_data = None
        step_count = 0

        logger.info(f"Response: {response}")
        for event in response.get("completion"):
            logger.info(f"Event: {event}")
            if "chunk" in event:
                logger.info("Processing chunk!")
                chunk = event["chunk"]
                completion = completion + chunk["bytes"].decode()
            elif "trace" in event:
                logger.info("Processing trace!")
                trace_obj = event["trace"]["trace"]
                if "orchestrationTrace" in trace_obj:
                    trace_dump = json.dumps(trace_obj["orchestrationTrace"], indent=2)
                    if "rationale" in trace_obj["orchestrationTrace"]:
                        step_count += 1
                        rationale_text = trace_obj["orchestrationTrace"]["rationale"][
                            "text"
                        ]
                        step_trace = f"\n---------- Step {step_count} ----------\n{rationale_text}"
                        print(f"step_trace: {step_trace}")
                        # with trace_col:
                        #     st.write(step_trace)
                    elif "modelInvocationInput" not in trace_obj["orchestrationTrace"]:
                        print(f"trace_dump: {trace_dump}")
                        # with trace_col:
                        #     st.write(trace_dump)
                elif "failureTrace" in trace_obj:
                    trace_dump = json.dumps(trace_obj["failureTrace"], indent=2)
                    print(f"trace_dump: {trace_dump}")
                elif "postProcessingTrace" in trace_obj:
                    step_count += 1
                    step_header = f"\n---------- Step {step_count} ----------\n"
                    print(f"step_header: {step_header}")
                    print(trace_obj)
                    # step_trace = f"{json.dumps(trace_obj['postProcessingTrace']['modelInvocationOutput'], indent=2)}"
                    step_trace = f"{json.dumps(trace_obj['postProcessingTrace']['modelInvocationOutput']['parsedResponse']['text'], indent=2)}"
                    print(step_trace)
                    # with trace_col:
                    #     st.write(step_header)
                    # with trace_col:
                    #     st.write(step_trace)
    except ClientError as e:
        logger.error(f"Couldn't invoke agent. {e}")
        raise

    return completion, trace_data


def decode_response(response):
    # Create a StringIO object to capture print statements
    print("Inside decode_response")
    captured_output = io.StringIO()
    print(f"{captured_output=}")
    sys.stdout = captured_output

    print(f"sys.stdout={sys.stdout}")
    # Your existing logic
    string = ""
    for line in response.iter_content():
        try:
            string += line.decode(encoding="utf-8")
        except:
            continue

    print("Decoded response", string)
    split_response = string.split(":message-type")
    print(f"Split Response: {split_response}")
    print(f"length of split: {len(split_response)}")

    for idx in range(len(split_response)):
        if "bytes" in split_response[idx]:
            # print(f"Bytes found index {idx}")
            encoded_last_response = split_response[idx].split('"')[3]
            decoded = base64.b64decode(encoded_last_response)
            final_response = decoded.decode("utf-8")
            print(final_response)
        else:
            print(f"no bytes at index {idx}")
            print(split_response[idx])

    last_response = split_response[-1]
    print(f"Lst Response: {last_response}")
    if "bytes" in last_response:
        print("Bytes in last response")
        encoded_last_response = last_response.split('"')[3]
        decoded = base64.b64decode(encoded_last_response)
        final_response = decoded.decode("utf-8")
    else:
        print("no bytes in last response")
        part1 = string[string.find("finalResponse") + len('finalResponse":') :]
        part2 = part1[: part1.find('"}') + 2]
        final_response = json.loads(part2)["text"]

    final_response = final_response.replace('"', "")
    final_response = final_response.replace("{input:{value:", "")
    final_response = final_response.replace(",source:null}}", "")
    llm_response = final_response

    # Restore original stdout
    sys.stdout = sys.__stdout__

    # Get the string from captured output
    captured_string = captured_output.getvalue()

    # Return both the captured output and the final response
    return captured_string, llm_response


def lambda_handler(event, context):

    sessionId = event["sessionId"]
    question = event["question"]
    endSession = False

    print(f"Session: {sessionId} asked question: {question}")

    try:
        if event["endSession"] == "true":
            endSession = True
    except:
        endSession = False

    url = f"https://bedrock-agent-runtime.{theRegion}.amazonaws.com/agents/{agentId}/agentAliases/{agentAliasId}/sessions/{sessionId}/text"

    try:
        response, trace_data = askQuestion2(question, sessionId, endSession)
        print(f"response={response}\n\ntrace_data={trace_data}")

        return {
            "status_code": 200,
            # "body": json.dumps({"response": response, "trace_data": trace_data})
            "body": json.dumps({"response": response, "trace_data": trace_data}),
        }
    except Exception as e:
        return {"status_code": 500, "body": json.dumps({"error": str(e)})}
