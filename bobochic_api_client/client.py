import os
import re
import io

import pandas as pd
import requests as rq

from . import (
    utils
)

class APIClient:
    BASE_URL = 'https://bobochicparis.com'

    def __init__(self, email, password):
        self._session = rq.Session()
        self._email = email
        self._password = password

        res = self._login()
        if res.status_code != 200:
            raise ValueError('Login Failed, check authentication ids')      

    @property
    def endpoints(self):
        return {
            'login': utils.urljoin(self.BASE_URL, 'supplier/login'),
            'commands_html': utils.urljoin(self.BASE_URL, 'supplier/commande'),
            'commands_export': utils.urljoin(self.BASE_URL, 'supplier/include/export.php'),
            'get_file': [
                utils.urljoin(self.BASE_URL, 'modules/relaiscolisam/files/in/etiquette/get_file.php'),
                utils.urljoin(self.BASE_URL, 'modules/virtransport/files/out/label/get_file.php'),
            ]
        }


    def fetch_commands(self):
        commands = []
        for ref, date, customer, phone, address, items, _, _, _ in self.commands_df.values:
            command = {
                'ref': ref,
                'date': date,
                'customer': customer.title() if customer else None,
                'phone': phone,
                'address': self._get_parsed_address(address),
                'items': self._get_parsed_items(items),
            }
            commands.append(command)
        return commands

    def _get_shipping_label_link(self, command_ref):
        for endpoint in self.endpoints.get('get_file', []):
            url = '{}?file={}.pdf'.format(endpoint, command_ref)
            if self._session.get(url).status_code == 200:
                return url
        return ''

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
        sku_pattern = r'([\d]+) x.+?REF.+?([\d]+[A-Z]{0,2}[\d]{0,1})'
        values = re.findall(sku_pattern, items)
        ean = False
        if len(values) == 0:
            ean = True
            ean_pattern = r'([\d]+) x.+?EAN.+?([\d]{13})'
            values = re.findall(ean_pattern, items)
        # pattern = r'([\d]+) x.+?EAN.+?([\d]{13}).+?REF.+?([\d]+[A-Z]{0,2}[\d]{0,1})'
        parsed_items = [
            {
                'sku': sku if not ean else None,
                'qty': qty,
                'barcode': sku if ean else None
            } for (qty, sku) in values
        ]
        return parsed_items if len(parsed_items) > 0 else []

    def _login(self):
        login_url = self.endpoints.get('login')
        login_data = {
            'EMAIL': self._email,
            'PASSWORD': self._password,
        }
        return self._session.post(login_url, data=login_data)

    @property
    def commands_df(self):
        if not hasattr(self, '_commands_df'):
            res = self._session.get(self.endpoints.get('commands_export'))
            if res.status_code != 200:
                raise ValueError('Commands export Failed!')
            with io.BytesIO(res.content) as fh:
                self._commands_df = pd.io.excel.read_excel(fh)
            self._commands_df = self._commands_df.where(pd.notnull(self._commands_df), None)

        return self._commands_df