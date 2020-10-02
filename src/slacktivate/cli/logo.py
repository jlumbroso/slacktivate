
import base64




#
_SLACK_LOGO_10_LINE_COLOR_BYTES = """
    G1swbSAgICAgG1szNm3iloTilojilojiloQbWzM3bSAbWzMybeKWhOKWiOKWiO
    KWhBtbMzdtDQogICAgIBtbMzZt4paA4paI4paI4paIG1szN20gG1szMm3iloji
    lojilojilogbWzM3bQ0KIBtbMzZt4paE4paE4paE4paE4paE4paE4paEG1szN2
    0gIBtbMzJt4paI4paI4paI4paIG1szN20gIBtbMzJt4paE4paEG1szN20NChtb
    MzZt4paI4paI4paI4paI4paI4paI4paI4paI4paIG1szN20gG1szMm3ilojilo
    jilojilogbWzM3bSAbWzMybeKWiOKWiOKWiOKWiBtbMzdtDQogG1szNm3iloDi
    loDiloDiloDiloDiloDiloAbWzM3bSAgIBtbMzJt4paA4paAG1szN20gIBtbMz
    Jt4paA4paA4paAG1szN20NChtbMzFt4paE4paI4paI4paIG1szN20gG1szMW3i
    loTilojilojiloQbWzM3bSAbWzMzbeKWhOKWiOKWiOKWiOKWiOKWiOKWiOKWiO
    KWhBtbMzdtDQobWzMxbeKWgOKWiOKWiOKWgBtbMzdtIBtbMzFt4paI4paI4paI
    4paIG1szN20gG1szM23iloDilojilojilojilojilojilojilojiloAbWzM3bQ
    0KICAgICAbWzMxbeKWiOKWiOKWiOKWiBtbMzdtIBtbMzNt4paE4paE4paEG1sz
    N20NCiAgICAgG1szMW3ilojilojilojilogbWzM3bSAbWzMzbeKWiOKWiOKWiO
    KWiBtbMzdtDQogICAgICAbWzMxbeKWgOKWgBtbMzdtICAgG1szM23iloDiloAb
    WzM3bQ==
    """

_SLACK_LOGO_10_LINES_COLOR = base64.b64decode(
    _SLACK_LOGO_10_LINE_COLOR_BYTES).decode("utf8")

SLACK_LOGO_10L = _SLACK_LOGO_10_LINES_COLOR

SLACKTIVATE_LOGO_6L = """
███████╗██╗      █████╗  ██████╗██╗  ██╗████████╗██╗██╗   ██╗ █████╗ ████████╗███████╗
██╔════╝██║     ██╔══██╗██╔════╝██║ ██╔╝╚══██╔══╝██║██║   ██║██╔══██╗╚══██╔══╝██╔════╝
███████╗██║     ███████║██║     █████╔╝    ██║   ██║██║   ██║███████║   ██║   █████╗  
╚════██║██║     ██╔══██║██║     ██╔═██╗    ██║   ██║╚██╗ ██╔╝██╔══██║   ██║   ██╔══╝  
███████║███████╗██║  ██║╚██████╗██║  ██╗   ██║   ██║ ╚████╔╝ ██║  ██║   ██║   ███████╗
╚══════╝╚══════╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═══╝  ╚═╝  ╚═╝   ╚═╝   ╚══════╝
"""[1:-1]

