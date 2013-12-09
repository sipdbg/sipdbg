# source: http://free.oxymium.net/Asterisk/SIPCodes.html
sip_codes = {
    # 1xx Informational"
    100: "Trying",
    180: "Ringing",
    181: "Call Is Being Forwarded",
    182: "Queued",
    # 2xx Success"
    200: "OK",
    # 3xx Redirection"
    300: "Multiple Choices",
    301: "Moved Permanently",
    302: "Moved Temporarily",
    303: "See Other",
    305: "Use Proxy",
    380: "Alternative Service",
    # 4xx Client Error"
    400: "Bad Request",
    401: "Unauthorized",
    402: "Payment Required",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    406: "Not Acceptable",
    407: "Proxy Authentication Required",
    408: "Request Timeout",
    409: "Conflict",
    410: "Gone",
    411: "Length Required",
    413: "Request Entity Too Large",
    414: "Request-URI Too Large",
    415: "Unsupported Media Type",
    420: "Bad Extension",
    480: "Temporarily not available",
    481: "Call Leg/Transaction Does Not Exist",
    482: "Loop Detected",
    483: "Too Many Hops",
    484: "Address Incomplete",
    485: "Ambiguous",
    486: "Busy Here",
    # 5xx Server Error"
    500: "Internal Server Error",
    501: "Not Implemented",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Time-out",
    505: "SIP Version not supported",
    # 6xx General Error"
    600: "Busy Everywhere",
    603: "Decline",
    604: "Does not exist anywhere",
    606: "Does not exist anywhere"
}
