# aws-ec2-scheduler
A simple Lambda function to start/stop EC2 instances on a schedule.

## How does it work?

You can either copy scheduler.py into a Lambda function, or upload it as a Layer if you want to use it across multiple functions.

In your main Lambda function, you can run the scheduler like so:

```python
import scheduler

def handler (event, context):
    scheduler.run(
        optin=True,
        action='start',
        region='us-east-1'
    )
```

This will cause any EC2 instances that have a 'Schedule' tag on them to start.  The intended implementation is two Cloudwatch events that send a 'start' or 'stop' action to the Lambda function at the respective times and days.  In that case, your action would be populated by ``event['action']``.

## Organizations and Cross-Accounts

The scheduler is set up for organizations with multiple accounts that they want to manage.  Create an IAM role on the target account that has, at minimum, the following permissions:

- ec2:Start*
- ec2:Stop*
- ec2:Describe*
- autoscaling:Describe*

Then set up the Trust Relationship so that the main account with the scheduler on it can access the target account's resources.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::<MAIN_ACCOUNT_ID>:root"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```


Copy the new IAM role's ARN into your scheduler configuration with an optional session name for audit log purposes.

```python
import scheduler

def handler (event, context):
    scheduler.run(
        optin=True,
        action='start',
        region='us-east-1'.
        role_arn='arn:aws:iam::<TARGET_ACCOUNT_ID>:role/<IAM_ROLE_NAME>',
        session='ec2scheduler'
    )
```
