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