
DATABASES = {
    'default': {
        'ENGINE': 'mysql.connector.django',
        'NAME': 'django_tests',
        'USER': 'root',
        'PASSWORD': '',
        'HOST': '127.0.0.1',
        'PORT': 13001,
        'TEST_CHARSET': 'utf8',
        'TEST_COLLATION': 'utf8_general_ci',
    },
    'other': {
        'ENGINE': 'mysql.connector.django',
        'NAME': 'django_tests',
        'USER': 'root',
        'PASSWORD': '',
        'HOST': '127.0.0.1',
        'PORT': 13002,
        'TEST_CHARSET': 'utf8',
        'TEST_COLLATION': 'utf8_general_ci',
        'TEST_MIRROR': 'default',
    }
}

SECRET_KEY = "django_tests_secret_key"
TIME_ZONE = 'UTC'
USE_TZ = False
SOUTH_TESTS_MIGRATE = False
