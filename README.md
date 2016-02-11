# Backup2Glacier
Backup data using AWS Glacier - Zealous-octo-rutabaga

#### Dependencies: ####

**Python 3**

**AWS Command Line Interface** - https://github.com/aws/aws-cli

**BOTO** - https://github.com/boto/boto3 http://aws.amazon.com/sdk-for-python/

    $ pip install awscli
    $ pip install boto3


#### Configuration ####

Set up credentials in `~/.aws/credentials`:

    [default]
    aws_access_key_id = YOUR_KEY
    aws_secret_access_key = YOUR_SECRET

Then, set up a default region in `~/.aws/config`:

    [default]
    region=us-east-1


#### Command Line ####
-d: Directory to be uploaded to Glacier (Using: Multipart Upload, Default Vault Name)
