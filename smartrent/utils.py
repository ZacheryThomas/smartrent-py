import asyncio
import re
import html
import json
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)

SMARTRENT_SESSIONS_URI = 'https://control.smartrent.com/api/v2/sessions'
SMARTRENT_HUBS_URI = 'https://control.smartrent.com/api/v2/hubs'
SMARTRENT_HUBS_ID_URI = 'https://control.smartrent.com/api/v2/hubs/{}/devices'


class SmartRentError(Exception):
    '''
    Base error for SmartRent
    '''

    pass


class InvalidAuthError(SmartRentError):
    '''
    Error related to invalid auth
    '''

    pass


class Client():
    def __init__(self, email: str, password: str, aiohttp_session:aiohttp.ClientSession):
        self._email = email
        self._password = password

        self._im_session_owner = bool(aiohttp_session)
        self._aiohttp_session = aiohttp_session if aiohttp_session else aiohttp.ClientSession()
        self.token = None


    def __del__(self):
        if not self._aiohttp_session.closed and self._im_session_owner:
            _LOGGER.info('%s: closing session %s', self._name, self._aiohttp_session)
            asyncio.create_task(self._aiohttp_session.close())


    async def async_get_devices_data(self) -> dict:
        res = await self._async_get_devices_data()
        if not res:
            _LOGGER.warn('No devices returned. Trying again with updated token...')
            await self._async_refresh_token()

            res = await self._async_get_devices_data()
        return res


    async def _async_get_devices_data(self) -> dict:
        '''Gets device dictonary from SmartRents `/resident` page

        ``email`` is the email address for your SmartRent account

        ``password`` you know what it is

        ``aiohttp_session`` uses the aiohttp_session that is passed in
        '''

        hubs_resp = await self._aiohttp_session.get(
            SMARTRENT_HUBS_URI,
            headers = {
                'authorization': f'Bearer {self.token}'
            }
        )
        hubs = await hubs_resp.json()

        devices_list = []
        for hub in hubs:
            devices_resp = await self._aiohttp_session.get(
                SMARTRENT_HUBS_ID_URI.format(hub['id']),
                headers = {
                    'authorization': f'Bearer {self.token}'
                }
            )
            devices = await devices_resp.json()

            for device in devices:
                _LOGGER.info('Found %s: %s', device['id'], device['name'])
                devices_list.append(device)

        return devices_list

    async def _async_refresh_token(self) -> None:
        '''Gets websocket token from SmartRents `/resident` page

        ``email`` is the email address for your SmartRent account

        ``password`` you know what it is

        ``aiohttp_session`` uses the aiohttp_session that is passed in
        '''
        result = await self._aiohttp_session.post(
            SMARTRENT_SESSIONS_URI,
            json={
                'email': self._email,
                'password': self._password
            }
        )

        result = await result.json()
        if not result.get('errors'):
            self.token = result['access_token']
        else:
            error_description = result['errors']['description']
            raise Exception(f'Token not retrieved! Loggin probably not successful: {error_description}')
