import os
import random
import string
from ecommerce.settings import MEDIA_ROOT

def path_and_rename(instance, filename):
    ext = filename.split('.')[-1]
    filename = f'{instance.category.pk}_{instance.pk}.{ext}'
    os.remove(os.path.join(MEDIA_ROOT, filename))
    return f'{filename}'


def group_image(instance, filename):
    ext = filename.split('.')[-1]
    filename = f'group_{instance.pk}.{ext}'
    try:
        os.remove(os.path.join(MEDIA_ROOT, filename))
    except:
        pass
    return f'{filename}'


def category_image(instance, filename):
    ext = filename.split('.')[-1]
    filename = f'catetory_{instance.pk}.{ext}'
    try:
        os.remove(os.path.join(MEDIA_ROOT, filename))
    except:
        pass
    return f'{filename}'


def get_random_session():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=36))
