import asyncio
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)

SMARTRENT_BASE_URI     = 'https://control.smartrent.com/api/v2/'
SMARTRENT_SESSIONS_URI = SMARTRENT_BASE_URI + 'sessions'
SMARTRENT_HUBS_URI     = SMARTRENT_BASE_URI + 'hubs'
SMARTRENT_HUBS_ID_URI  = SMARTRENT_BASE_URI + 'hubs/{}/devices'


class SmartRentError(Exception):
    '''
    Base error for SmartRent
    '''


class InvalidAuthError(SmartRentError):
    '''
    Error related to invalid auth
    '''


class Client():
    def __init__(
        self,
        email: str,
        password: str,
        aiohttp_session:aiohttp.ClientSession
    ):
        '''
        Represents Cleint for SmartRent api.
        Usually shared between multiple devices for best performance.

        ``email`` is the email address for your SmartRent account

        ``password`` you know what it is

        ``aiohttp_session`` (optional) uses the aiohttp_session that is passed in
        '''
        self._email = email
        self._password = password

        self._im_session_owner = not bool(aiohttp_session)
        self._aiohttp_session = aiohttp_session if aiohttp_session else aiohttp.ClientSession()
        self.token = None


    def __del__(self):
        '''
        Handles delete of aiohttp session if class is tasked with it
        '''
        if not self._aiohttp_session.closed and self._im_session_owner:
            _LOGGER.info('%s: closing aiohttp session %s', str(self), self._aiohttp_session)
            asyncio.run(self._aiohttp_session.close())


    async def async_get_devices_data(self) -> dict:
        '''
        Gets device dictonary from SmartRent's api.
        Also handles retry if token is bad
        '''
        res = await self._async_get_devices_data()
        if not res:
            _LOGGER.warning('No devices returned. Trying again with updated token...')
            await self.async_refresh_token()

            res = await self._async_get_devices_data()
        return res


    async def _async_get_devices_data(self) -> dict:
        '''
        Gets device dictonary from SmartRent's api
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


    async def async_refresh_token(self) -> None:
        '''
        Refreshes API token from SmartRents
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
            raise Exception(
                'Token not retrieved! '
                f'Loggin probably not successful: {result["errors"]}'
            )
