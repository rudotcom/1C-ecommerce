import os
import re
import time
from ecommerce.settings import BASE_DIR, SITE_URL
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from store.models import Category, Product
from lxml import etree as ET
import csv
from ecommerce.celery import celery_app


def file_older_than(filepath, age):
    return time.time() - os.path.getmtime(filepath) > age


def atol_import(file_name):
    file_path = os.path.join(BASE_DIR, file_name)

    if os.path.exists(file_path):
        with open(file_path, 'r', encoding="cp1251", errors='ignore') as f:
            reader = csv.reader(f, delimiter=';')
            print(f'{file_name} import started')

            for row in reader:
                if len(row) < 25:  # строка содержит меньше 25  полей - игнорируем
                    continue
                try:
                    key = row[0]
                    article = row[25]
                    price = row[4]
                    name = row[2]
                    parent = row[15]

                    # Удаляем круглые скобки в начале Наименования
                    name = re.sub(r'^\([^)]+\)\s*', '', name)

                    if len(name) < 2:  # Длина наименования меньше 2 - игнорируем
                        continue
                    if len(article) == 0 and len(price) == 0:
                        name = re.sub(r'\([^)]+\)\.*', '', name)
                        category, created = Category.objects.get_or_create(id=key)
                        category.name = name
                        category.save()
                    else:
                        category = Category.objects.get(id=parent)
                        product, created = Product.objects.get_or_create(id=key, category=category)
                        product.title = name
                        product.article = article
                        product.price = float(price)
                        product.save()
                        # print(f'OK\t{product.id}, {product.title}')

                except Exception as e:
                    print(f'{e}\n\t{row}')
        try:
            os.remove(file_path)
        except FileExistsError:
            print(f'No file to process ({file_path})')


def xml_import(file_name):
    file_path = os.path.join(BASE_DIR, file_name)
    if os.path.exists(file_path):
        parser = ET.XMLParser(encoding='cp1251')
        root = ET.parse(file_path, parser).getroot()

        denied = 0

        print(f'{file_name} import started')
        for node in root.findall('nom'):
            name = node.get('name')
            id = node.get('id')
            # article = node.get('art')
            whs = []
            for sub in node.findall('whs/scl'):
                whs.append(sub.get("count"))

            try:
                product = Product.objects.get(id=id)
                product.warehouse1 = whs[0]
                product.warehouse2 = whs[1]
                product.save()
                # print(f'OK\tid: {id}, name: {name}, whs: {whs}')
            except Exception as e:
                denied += 1
                # Товары, которых не оказалось в alol файле (без категорий) отбрасываются
                # print(f'{e}\n\t{id} {name}: {whs}')

        if denied:
            print('Не найдено по ID:', denied)
        try:
            os.remove(file_path)
        except FileExistsError:
            print(f'No file to process ({file_path})')


@celery_app.task
def product_import():
    """TODO: записывать результат в файл"""
    LOCK_TIME = 60 * 120
    lock_file = os.path.join(BASE_DIR, 'imported/.importlock')
    """
    Файл блокироваки процесса. Если процесс был запущен более чем 2 часа
    назад, значит он умер. Удалить файл блокировки
    """
    if os.path.exists(lock_file):
        if file_older_than(lock_file, LOCK_TIME):
            os.remove(lock_file)
        else:
            print('Import is still being processed...')
            return

    open(lock_file, 'a').close()

    # Путь к файлу от корня проекта
    atol_import('imported/export_atol.txt')
    xml_import('imported/export.xml')
    try:
        os.remove(lock_file)
    except FileExistsError:
        print(f'No lock file: ({lock_file})')


def send_confirmation_email(email, code):
    # Отправить письмо с кодом подтверждения
    html = render_to_string('email_confirm.html',
                            {'code': code,
                             'site_url': SITE_URL})

    subject = 'Подтвердите адрес своей электронной почты!'
    from_email, to = 'Электр{он/ика}<store@as-electrica.ru>', email
    text_content = 'Подтвердите адрес своей электронной почты в магазине Электр{он/ика}!'

    msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
    msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=False)


def send_order_email(email, order):
    html = render_to_string('email_order_placed.html',
                            {'order': order,
                             'site_url': SITE_URL})

    subject = 'Заказ в магазине Электр{он/ика}'
    from_email, to = 'Электр{он/ика}<store@as-electrica.ru>', email
    text_content = 'Спасибо за Ваш заказ в магазине Электр{он/ика}!'

    msg = EmailMultiAlternatives(subject, text_content, from_email, [to, ])
    msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=False)


def send_order_personnel_email(order):
    html = render_to_string('email_order_personnel.html',
                            {'order': order,
                             'site_url': SITE_URL})

    subject = f'Новый заказ №{order.id} в магазине Электр{{он/ика}}'
    from_email, to = 'Электр{он/ика}<store@as-electrica.ru>', 'sales@as-electrica.ru'
    text_content = 'Новый заказ в магазине Электр{он/ика}!'

    msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
    msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=False)


def send_order_is_ready_email(order):
    email = order.owner.email
    html = render_to_string('email_order_is_ready.html',
                            {'order': order,
                             'site_url': SITE_URL})

    subject = 'Электр{он/ика}: Ваш заказ готов к выдаче'
    from_email, to = 'Электр{он/ика}<store@as-electrica.ru>', email
    text_content = 'Ваш заказ в магазине Электр{он/ика} готов к выдаче!'

    msg = EmailMultiAlternatives(subject, text_content, from_email, [to, ])
    msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=False)
