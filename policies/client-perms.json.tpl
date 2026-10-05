{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DiscoverFileSystemsByTag",
      "Effect": "Allow",
      "Action": ["elasticfilesystem:DescribeFileSystems", "elasticfilesystem:DescribeAccessPoints",
                 "elasticfilesystem:DescribeMountTargets", "fsx:DescribeFileSystems"],
      "Resource": "*"
    },
    {
      "Sid": "ReadTheTwoTestUsersPasswordsOnly",
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": [
        "arn:aws:secretsmanager:@@REGION@@:@@ACCOUNT_ID@@:secret:kgotla/ad-thabo-*",
        "arn:aws:secretsmanager:@@REGION@@:@@ACCOUNT_ID@@:secret:kgotla/ad-lerato-*"
      ]
    },
    {
      "Sid": "ActuarialDatasetBucket",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::@@BUCKET@@"
    },
    {
      "Sid": "ActuarialDatasetObjects",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::@@BUCKET@@/actuarial/*"
    }
  ]
}
