import re
import html
import json
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)

SMARTRENT_AUTHENTICATION_URI = 'https://control.smartrent.com/authentication/sessions'
SMARTRENT_RESIDENT_PAGE_URI = 'https://control.smartrent.com/resident'


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


async def async_login_to_api(email:str, password:str, aiohttp_session:aiohttp.ClientSession) -> str:
    '''Logs into SmartRents api with the provided session

    ``email`` is the email address for your SmartRent account

    ``password`` you know what it is

    ``aiohttp_session`` uses the aiohttp_session that is passed in
    '''
    _LOGGER.debug(f'Attempting login')
    resp = await aiohttp_session.post(SMARTRENT_AUTHENTICATION_URI, json={
        'email': email,
        'password': password
    })

    json = await resp.json()

    if json.get('error', '') == 'invalid_credentials':
        raise InvalidAuthError("Invalid credentials")


async def async_get_resident_page_text(email:str, password:str, aiohttp_session:aiohttp.ClientSession) -> str:
    '''Gets full text from `/resident` page

    ``email`` is the email address for your SmartRent account

    ``password`` you know what it is

    ``aiohttp_session`` uses the aiohttp_session that is passed in
    '''

    _LOGGER.debug('Calling resident page')
    response = await aiohttp_session.get(SMARTRENT_RESIDENT_PAGE_URI)
    response_text = await response.text()

    if 'You must login to access this page' in response_text:
        _LOGGER.warning(f'Session no longer logged in. Attempting login')
        await async_login_to_api(email, password, aiohttp_session)

        response = await aiohttp_session.get(SMARTRENT_RESIDENT_PAGE_URI)
        response_text = await response.text()

        if 'You must login to access this page' in response_text:
            raise Exception('Something is wrong with calling the "/resident" endpoint.')

    return response_text


async def async_get_devices_data(email:str, password:str, aiohttp_session:aiohttp.ClientSession) -> dict:
    '''Gets device dictonary from SmartRents `/resident` page

    ``email`` is the email address for your SmartRent account

    ``password`` you know what it is

    ``aiohttp_session`` uses the aiohttp_session that is passed in
    '''
    resident_page_text = await async_get_resident_page_text(email, password, aiohttp_session)

    matches = re.search(r'bundle-props="(.*)" ', resident_page_text)
    if matches:
        data = html.unescape(matches[1])
        data = json.loads(data)

        return data
    else:
        raise Exception('Devices not retrieved! Loggin probably not successful.')


async def async_get_token(email:str, password:str, aiohttp_session:aiohttp.ClientSession) -> str:
    '''Gets websocket token from SmartRents `/resident` page

    ``email`` is the email address for your SmartRent account

    ``password`` you know what it is

    ``aiohttp_session`` uses the aiohttp_session that is passed in
    '''
    resident_page_text = await async_get_resident_page_text(email, password, aiohttp_session)

    matches = re.search(r'websocketAccessToken = "(.*)"', resident_page_text)
    if matches:
        return matches[1]
    else:
        raise Exception('Token not retrieved! Loggin probably not successful.')
