import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)

async def get_resident_page_text(
    email, password, aiohttp_session:aiohttp.ClientSession=None
) -> str:
    '''Gets full text from `/resident` page

    ``email`` is the email address for your SmartRent account

    ``password`` you know what it is

    ``aiohttp_session`` if provided uses the aiohttp_session that is passed in.
    This helps to avoid having to authenticate as often. Otherwise calling this method
    without a session ensures you will call the `/authentication/sessions` endpoint
    '''

    async with aiohttp.ClientSession() as session:
        session = aiohttp_session if aiohttp_session else session

        _LOGGER.info('Calling resident page')
        response = await session.get('https://control.smartrent.com/resident')
        resp_text = await response.text()

        if 'You must login to access this page.' in resp_text:
            _LOGGER.info(f'Attempting login')
            await session.post('https://control.smartrent.com/authentication/sessions', json={
                'email': email,
                'password': password
            })

            _LOGGER.info('Calling resident page again')
            response = await session.get('https://control.smartrent.com/resident')

        return await response.text()
