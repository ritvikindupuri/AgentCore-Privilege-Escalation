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
  <b>Figure 1: High-Level Attack Architecture. The attack leverages a public-facing Code Interpreter to bridge the gap between a low-privilege external user and a high-privilege internal IAM role.</b>
</p>

---

## The Exploit Chain

### Phase 1: Initial Reconnaissance & Role Enumeration

Starting as a compromised IAM user with highly restricted permissions (primarily read-only console access and no S3 permissions), the first step was to understand the environment. I enumerated existing IAM roles, specifically looking for those associated with Bedrock services.

<p align="center">
  <img src=".assets/Privilege Boundary Proof.png" alt="Privilege Boundary Proof" width="800"/>
  <br>
  <b>Figure 2: Verifying execution context and identity. The initial `get-caller-identity` check confirms the initial execution context before escalation.</b>
</p>

<p align="center">
  <img src=".assets/Role Enumeration.png" alt="Role Enumeration" width="800"/>
  <br>
  <b>Figure 3: Role Enumeration. Identifying the target execution role by listing roles associated with Bedrock AgentCore execution contexts.</b>
</p>

### Phase 2: Identifying the Vulnerability (Overprivileged Policy)

Analysis of the discovered roles revealed a critical misconfiguration. One specific execution role, intended for a code interpreter, possessed an IAM policy with excessively broad read permissions to a production data S3 bucket.

The policy granted actions like `s3:GetObject` and `s3:ListBucket` on a sensitive resource without adequate scoping. This is the core vulnerability: giving a remote execution environment permissions it does not strictly need.

<p align="center">
  <img src=".assets/Overprivileged IAM Policy.png" alt="Overprivileged IAM Policy" width="800"/>
  <br>
  <b>Figure 4: Vulnerable IAM Policy. Note the wildcards allowing `s3:ListBucket` and `s3:GetObject` on a sensitive customer data S3 bucket, which enables the data exfiltration.</b>
</p>

### Phase 3: Weaponization (Creating the Rogue Interpreter)

To exploit this role, I utilized my limited permissions to create a **custom Bedrock AgentCore Code Interpreter** via the CLI. This bypassed the standard Agent creation flows and allowed me to bind the resource directly to the target execution role.

**Crucial Configuration Details:**
1.  **Execution Role:** Bound the overprivileged role found in Phase 2.
2.  **Network Mode:** Configured as **PUBLIC**, enabling direct API access without VPC restrictions.

<p align="center">
  <img src=".assets/Create the custom code interpreter.png" alt="Create the custom code interpreter" width="800"/>
  <br>
  <b>Figure 5: Weaponization Configuration. Manually binding the target high-privilege role to a new, public-facing interpreter instance to create an exploit primitive.</b>
</p>

### Phase 4: Execution & Privilege Escalation

With the interpreter active, I used a custom Python script to directly call the `invoke_code_interpreter` API. Instead of using a prompt to ask an LLM to write code, I passed raw Python commands that executed system shell instructions.

By executing `aws sts get-caller-identity` inside the interpreter runtime, I verified that the code was running under the assumed role of the Interpreter, confirming the privilege bypass.

<p align="center">
  <img src=".assets/Code interpreter exploit script.png" alt="Code interpreter exploit script" width="800"/>
  <br>
  <b>Figure 6: The Exploit Script. This Python code bypasses the agent layer to inject raw shell commands directly into the interpreter runtime via `boto3`.</b>
</p>

### Phase 5: Lateral Movement & Data Discovery

Having successfully assumed the high-privilege role, I used the exploit script to explore the S3 environment. The interpreter's role allowed me to bypass the restrictions on my original user account.

1.  **Bucket Discovery:** I executed `aws s3 ls` to list all buckets in the account.
2.  **Content Enumeration:** I targeted the sensitive bucket identified in the IAM policy.

<p align="center">
  <img src=".assets/List bucket contents.png" alt="List bucket contents" width="800"/>
  <br>
  <b>Figure 7: Lateral Movement. Using the stolen session to enumerate S3 buckets, revealing infrastructure invisible to the initial user.</b>
</p>

<p align="center">
  <img src=".assets/S3 access gained.png" alt="S3 access gained" width="800"/>
  <br>
  <b>Figure 8: S3 Access Verification. Validating that the `ListBucket` action succeeds against the restricted resource, confirming the permissions bypass is active.</b>
</p>

### Phase 6: Exfiltration (Impact)

The final step was proving access to sensitive data. A recursive listing of the target bucket revealed highly sensitive files, including customer profile and transaction datasets, which were completely inaccessible to the initial user.

<p align="center">
  <img src=".assets/Sensitive file listing.png" alt="Sensitive file listing" width="800"/>
  <br>
  <b>Figure 9: Data Exfiltration. The final impact proof: listing sensitive customer profile and transaction datasets that constitute a critical data breach.</b>
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

This project highlights a fundamental shift in cloud security: **AI Agents are now part of the identity perimeter.**

By demonstrating how a misconfigured Code Interpreter can be weaponized as a "serverless bastion host," I showed that securing GenAI is not just about prompt engineering or model safety—it is an infrastructure security challenge. The successful escalation from a limited user to full data access underscores the necessity of treating AI runtimes with the same zero-trust rigor as any other compute environment. Organizations must move beyond implicit trust and enforce strict network boundaries and IAM scoping to safely adopt these powerful capabilities.
