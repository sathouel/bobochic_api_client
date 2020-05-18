import os
import re

import pandas as pd
import requests as rq

from . import (
    utils,
    DATA_DIR
)

class APIClient:
    BASE_URL = 'https://bobochicparis.com'

    def __init__(self, email, password, data_dirpath=DATA_DIR):
        self._session = rq.Session()
        self._email = email
        self._password = password
        self._data_dirpath = data_dirpath

        res = self._login()
        if res.status_code != 200:
            raise ValueError('Login Failed, check authentication ids')      

    @property
    def endpoints(self):
        return {
            'login': utils.urljoin(self.BASE_URL, 'supplier/login'),
            'commands_html': utils.urljoin(self.BASE_URL, 'supplier/commande'),
            'commands_export': utils.urljoin(self.BASE_URL, 'supplier/include/export.php'),
            'get_file': utils.urljoin(self.BASE_URL, 'modules/relaiscolisam/files/in/etiquette/get_file.php')
        }


    def fetch_commands(self):
        self._export_commands_to_excel()
        commands = []
        for ref, date, customer, phone, address, items, _, _, _ in self.commands_df.values:
            command = {
                'ref': ref,
                'date': date,
                'customer': customer.title(),
                'phone': phone,
                'address': self._get_parsed_address(address),
                'items': self._get_parsed_items(items),
                'shipping_label_url': self._get_shipping_label_link(ref)
            }
            commands.append(command)
        return commands

    def _get_shipping_label_link(self, command_ref, check_valid_link=False):
        url = '{}?file={}.pdf'.format(self.endpoints.get('get_file'), command_ref)
        if check_valid_link and self._session.get(url).status_code != 200:
            url = None
        return url

    def _get_parsed_address(self, address):
        pattern = r'(.+?) ([\d]{4,5}) (.+?) \(FR\)'
        parsed_address = [
            {
                'address': address.title(),
                'zip_code': zip_code,
                'city': city.title(),
                'country': 'France'
            } for (address, zip_code, city) in re.findall(pattern, address)
        ]
        return parsed_address[0] if len(parsed_address) > 0 else {}

    def _get_parsed_items(self, items):
        pattern = r'([\d]+) x.+?REF.+?([\d]+[A-Z]*)'
        parsed_items = [
            {
                'sku': sku,
                'qty': qty
            } for (qty, sku) in re.findall(pattern, items)
        ]
        return parsed_items if len(parsed_items) > 0 else []

    def _login(self):
        login_url = self.endpoints.get('login')
        login_data = {
            'EMAIL': self._email,
            'PASSWORD': self._password,
        }
        return self._session.post(login_url, data=login_data)

    def _export_commands_to_excel(self):
        res = self._session.get(self.endpoints.get('commands_export'))
        if res.status_code != 200:
            raise ValueError('Commands export Failed!')

        export_filepath = os.path.join(self._data_dirpath, 'commands.xlsx')
        with open(export_filepath, "wb") as f:
            f.write(res.content)
            f.close()

    @property
    def commands_df(self):
        filepath = os.path.join(self._data_dirpath, 'commands.xlsx')
        if not os.path.exists(filepath):
            self._export_commands_to_excel()
        return pd.read_excel(filepath)