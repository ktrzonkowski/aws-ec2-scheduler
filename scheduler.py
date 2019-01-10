import boto3

def aws_session(role_arn=None, session_name='lambda_session'):
    """Creates an AWS boto3 session.

    By default, returns a session for the current account.
    Passing in a role_arn will allow for cross-account
    access, in the case of AWS Organizations.

    Args:
        role_arn (str): IAM Role ARN for the target account.
        session_name (str): Descriptor for the assumed role session
            to use for the purpose of audit logs.

    Returns:
        A boto3 session for managing AWS resources.
        
    Todo:
        * Document all possible exceptions
    """
    
    if role_arn:
        client = boto3.client('sts')
        response = client.assume_role(RoleArn=role_arn, RoleSessionName=session_name)
        session = boto3.Session(
            aws_access_key_id=response['Credentials']['AccessKeyId'],
            aws_secret_access_key=response['Credentials']['SecretAccessKey'],
            aws_session_token=response['Credentials']['SessionToken'])
        return session
    else:
        return boto3.Session()

def run(optin=True, action='start', region='us-east-1', role_arn=None, session_name=None, dryRun=False):
    """Runs the scheduler to start/stop EC2 instances.

    This function retrieves all of the EC2 instances in a given
    region for an account.
    
    To minimize accidental chaos, this function defaults to Opt-In
    Start, as opposed to an Opt-Out Stop that would stop every
    instance in an account that doesn't have a Schedule tag.
    
    If you want to see which instances would be affected without
    actually starting or stopping them, you can do a dry run instead.
    The instance IDs will still be returned and debug info will
    be printed to the console.

    Args:
        optin (bool): Opt-In or Opt-Out configuration
        action (str): Either 'start' or 'stop'
        region (str): The AWS region to use
        role_arn (str): See `aws_session` function above
        session_name (str): See `aws_session` function above
        dryRun (bool): No instances will be started or stopped

    Returns:
        A list of EC2 instance IDs that were affected.
        May return an empty list if none were found.
        
    Raises:
        ValueError: If 'action' is neither 'start' nor 'stop'
        
    Todo:
        * Allow for more customization and flexibility with the
            Schedule tag
        * Paginate the ASG results, just in case
        * What is the limit for how many instance IDs can be
            started/stopped in a single call?
        * Document all the potential Exceptions
    """

    if action != 'start' and action != 'stop':
        raise ValueError("action should be 'start' or 'stop'. The value of action was: {}".format(action))
    
    account = aws_session(role_arn=role_arn, session_name=session_name)

    # In the event that there are Autoscaling Groups being used,
    # we don't want to mess with them because the ASG will just panic.
    asg_client = account.client('autoscaling', region)
    asg_response = asg_client.describe_auto_scaling_instances()
    asg_instances = list()
    
    for r in asg_response['AutoScalingInstances']:
        asg_instances.append(r['InstanceId'])

    # Time to grab all of the account's EC2 instances!
    ec2_client = account.client('ec2', region)
    ec2_paginator = ec2_client.get_paginator('describe_instances')
    ec2_response = ec2_paginator.paginate().build_full_result()
    ec2_instances = list()
    
    for r in ec2_response['Reservations']:
        for i in r['Instances']:
            # Ensure this instance isn't part of an ASG
            if i['InstanceId'] not in asg_instances:
                # If it's not running or stopped, it may be in the middle of something.
                # Leave it alone, in that case.
                if i['State']['Name'] == "running" or i['State']['Name'] == "stopped":
                    hasTag = False
                
                    # Check the instance's tags for a Schedule tag
                    # ... but don't assume it has a 'Tags' attribute, because some don't
                    if 'Tags' in i:
                        for t in i['Tags']:
                            if t['Key'] == "Schedule":
                                hasTag = True
                                break
    
                    # If we are Opt-In and have the Schedule tag...
                    # OR we are Opt-Out and DON'T have the Schedule tag...
                    if (optin and hasTag) or (not optin and not hasTag):
                        ec2_instances.append(i['InstanceId'])

    # Now it's finally time to do the magic!
    if dryRun:
        print('This would perform the {} action on {} instances'.format(action, len(ec2_instances)))
    else:
        if (len(ec2_instances) > 0):
            if action == "start":
                ec2_client.start_instances(InstanceIds=ec2_instances)
            elif action == "stop":
                ec2_client.stop_instances(InstanceIds=ec2_instances)
    
    return ec2_instances
