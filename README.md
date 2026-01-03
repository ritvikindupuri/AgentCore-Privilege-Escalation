# AWS Bedrock Privilege Escalation: Exploiting Overprivileged Code Interpreters

**Disclaimer:** This project was conducted in a controlled, ethical lab environment for educational and security research purposes. No actual customer data was compromised in the creation of this demonstration.

## Executive Summary

This project demonstrates a critical cloud security vulnerability class: **Direct Code Interpreter Abuse**. By exploiting an overprivileged execution role attached to an **AWS Bedrock AgentCore Code Interpreter**, I successfully elevated privileges from a limited IAM user with zero S3 access to full read access on sensitive customer data buckets.

Unlike typical LLM attacks that rely on "tricking" a model (prompt injection), this exploit leverages a control-plane misconfiguration. I demonstrated that if a Code Interpreter is configured in **PUBLIC** network mode with an overprivileged role, an attacker can directly invoke the `invoke_code_interpreter` API. This permits the execution of arbitrary Python shell commands without any prompt filtering or agent-based reasoning, effectively bypassing IAM privilege boundaries.

---

## Technology Stack

* **Cloud Infrastructure:** AWS Bedrock AgentCore (Code Interpreters), AWS IAM, AWS S3, AWS STS
* **Development & Exploitation:** Python 3.x, Boto3 (AWS SDK)
* **Attack Vectors:** Overprivileged IAM Roles, Direct API Invocation, Arbitrary Code Execution
* **Security Frameworks:** MITRE ATT&CK (Privilege Escalation, Execution, Discovery)

---

## Architecture & Attack Path

The following diagram illustrates the attack flow, from the initial limited user to the final exfiltration of sensitive data stored in S3.

<p align="center">
  <img src=".assets/Architecture diagram.png" alt="Architecture Diagram" width="800"/>
  <br>
  <b>Figure 1: High-Level Attack Architecture</b>
  <br><br>
  This diagram visualizes the privilege escalation path. The attack leverages a public-facing Bedrock Code Interpreter to bridge the gap between a low-privilege external user (who has no direct S3 access) and a high-privilege internal IAM Execution Role (which has full S3 read access). The Code Interpreter acts as a serverless proxy, executing commands on behalf of the attacker.
</p>

---

## The Exploit Chain

### Phase 1: Initial Reconnaissance & Role Enumeration

Starting as a compromised IAM user with highly restricted permissions (primarily read-only console access and no S3 permissions), the first step was to understand the environment. I enumerated existing IAM roles, specifically looking for those associated with Bedrock services.

<p align="center">
  <img src=".assets/Privilege Boundary Proof.png" alt="Privilege Boundary Proof" width="800"/>
  <br>
  <b>Figure 2: Execution Context Verification</b>
  <br><br>
  This console output establishes the baseline for the exploit. By running `get-caller-identity`, I confirmed that my initial session was restricted to the compromised user context. Attempting to list S3 buckets at this stage resulted in an "Access Denied" error, proving that any subsequent data access must be the result of a successful privilege escalation.
</p>

<p align="center">
  <img src=".assets/Role Enumeration.png" alt="Role Enumeration" width="800"/>
  <br>
  <b>Figure 3: Role Enumeration</b>
  <br><br>
  Using the AWS CLI, I filtered the available IAM roles to identify potential targets. The output reveals the `AgentCodeInterpreterRole`, a role specifically designed to be assumed by Bedrock resources. Discovering this role provided the specific target ARN needed to configure the rogue interpreter in the next phase.
</p>

### Phase 2: Identifying the Vulnerability (Overprivileged Policy)

Analysis of the discovered roles revealed a critical misconfiguration. One specific execution role, intended for a code interpreter, possessed an IAM policy with excessively broad read permissions to a production data S3 bucket.

<p align="center">
  <img src=".assets/Overprivileged IAM Policy.png" alt="Overprivileged IAM Policy" width="800"/>
  <br>
  <b>Figure 4: Vulnerable IAM Policy Configuration</b>
  <br><br>
  This JSON policy document highlights the root cause of the vulnerability. The policy grants `s3:ListBucket` and `s3:GetObject` permissions on the sensitive `customer-data` bucket. Critically, these permissions are not scoped to a specific prefix (e.g., a "safe" folder), allowing any entity assuming this role to read the entire contents of the bucket.
</p>

### Phase 3: Weaponization (Creating the Rogue Interpreter)

To exploit this role, I utilized my limited permissions to create a **custom Bedrock AgentCore Code Interpreter** via the CLI. This bypassed the standard Agent creation flows and allowed me to bind the resource directly to the target execution role.

<p align="center">
  <img src=".assets/Create the custom code interpreter.png" alt="Create the custom code interpreter" width="800"/>
  <br>
  <b>Figure 5: Weaponization and Interpreter Creation</b>
  <br><br>
  This screenshot shows the `aws bedrock-agentcore-control` command used to instantiate the malicious resource. Key configuration parameters include setting `networkMode: PUBLIC`, which exposes the interpreter to direct API calls over the internet, and binding it to the overprivileged `AgentCodeInterpreterRole` identified in Phase 1.
</p>

### Phase 4: Execution & Privilege Escalation

With the interpreter active, I used a custom Python script to directly call the `invoke_code_interpreter` API. Instead of using a prompt to ask an LLM to write code, I passed raw Python commands that executed system shell instructions.

<p align="center">
  <img src=".assets/Code interpreter exploit script.png" alt="Code interpreter exploit script" width="800"/>
  <br>
  <b>Figure 6: The Exploit Script</b>
  <br><br>
  This custom Python script uses the `boto3` library to bypass the conversational agent layer entirely. It constructs a payload containing raw Python code (`os.popen`) that executes arbitrary shell commands inside the remote interpreter runtime. This allows me to use the interpreter as a "serverless shell" running with the full privileges of the attached IAM role.
</p>

### Phase 5: Lateral Movement & Data Discovery

Having successfully assumed the high-privilege role, I used the exploit script to explore the S3 environment. The interpreter's role allowed me to bypass the restrictions on my original user account.

<p align="center">
  <img src=".assets/List bucket contents.png" alt="List bucket contents" width="800"/>
  <br>
  <b>Figure 7: Lateral Movement & Enumeration</b>
  <br><br>
  Using the stolen session, I executed `aws s3 ls` to enumerate all buckets in the account. This step reveals infrastructure that was completely invisible to the initial limited user, effectively mapping the attack surface for further data exfiltration.
</p>

<p align="center">
  <img src=".assets/S3 access gained.png" alt="S3 access gained" width="800"/>
  <br>
  <b>Figure 8: S3 Access Verification</b>
  <br><br>
  This screenshot confirms the successful bypass of IAM boundaries. While the initial user was denied access, the Code Interpreter session successfully lists the contents of the restricted bucket. The output verifies that the session is authenticated as `AssumedRole/AgentCodeInterpreterRole` and authorized to perform the `ListBucket` action.
</p>

### Phase 6: Exfiltration (Impact)

The final step was proving access to sensitive data. A recursive listing of the target bucket revealed highly sensitive files, including customer profile and transaction datasets, which were completely inaccessible to the initial user.

<p align="center">
  <img src=".assets/Sensitive file listing.png" alt="Sensitive file listing" width="800"/>
  <br>
  <b>Figure 9: Data Exfiltration Impact</b>
  <br><br>
  The final proof of impact. By recursively listing the target bucket, I uncovered sensitive PII files (`customer_profiles.csv`, `financial_transactions.csv`). This demonstrates that the vulnerability leads to a critical data breach, allowing an attacker to exfiltrate proprietary and regulated data.
</p>

---

## Root Cause Analysis & Threat Model

The root cause of this vulnerability is a failure in **Identity and Access Management (IAM) configuration** coupled with **Implicit Trust** in the Code Interpreter runtime.

* **Direct Execution Risk:** The ability to instantiate a Code Interpreter with a PUBLIC endpoint allows attackers to treat it as a "Serverless Shell," executing arbitrary code without going through an Agent's reasoning layer.
* **Violation of Least Privilege:** The execution role was granted broad S3 read access to a sensitive customer data bucket instead of being scoped down to only the specific prefix required for legitimate tasks.
* **Implicit Trust:** The architecture assumed that only "safe" code generated by an LLM would run on the interpreter. By accessing the API directly, this assumption was invalidated.

---

## Mitigations & Best Practices

To prevent this type of privilege escalation, organizations must apply rigorous security controls:

1.  **Strict Least Privilege for Execution Roles:**
    * Interpreter execution roles should only have the *bare minimum* permissions required.
    * Scope S3 access down to specific buckets and prefixes.

2.  **Restrict `iam:PassRole`:**
    * Ensure users cannot pass high-privilege roles to Bedrock resources. This prevents an attacker from binding a powerful role to a malicious interpreter.

3.  **Network Isolation:**
    * Disable PUBLIC network mode for Code Interpreters. Use VPC endpoints to restrict invocation access to internal network traffic only.

4.  **Monitor `invoke_code_interpreter`:**
    * Monitor CloudTrail for direct API calls to `InvokeCodeInterpreter`. Legitimate workflows typically go through an Agent (`InvokeAgent`); direct interpreter usage may indicate an exploit attempt.

---

## Conclusion

This project reinforced an important takeaway: **AI runtimes must be treated like any other compute boundary. Prompt safety alone doesn’t protect against infrastructure-level misconfiguration.**

While organizations often focus on preventing "jailbreaks" (getting the LLM to say bad things), the real danger lies in the runtime environment itself. If these misconfigurations were exploited in a production environment, the consequences would be severe:

* **Massive Data Exfiltration:** An attacker could recursively sync sensitive S3 buckets containing PII, financial records, or intellectual property, leading to heavy regulatory fines (GDPR/CCPA) and reputational damage.
* **Lateral Movement:** If the attached role had broader permissions (e.g., `secretsmanager:GetSecret` or `dynamodb:Scan`), the Code Interpreter would serve as a pivot point to compromise internal databases and retrieve production credentials.
* **Denial of Service & Resource Hijacking:** The ability to execute arbitrary Python code allows attackers to hijack compute resources for tasks like crypto mining or to disrupt business logic flows that rely on these agents.

Ultimately, securing GenAI requires a "Defense in Depth" approach—enforcing strict network isolation (VPC) and rigorous IAM scoping—rather than relying solely on the model's refusal to answer malicious prompts.
