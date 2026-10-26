from retail.prepare import prepare
from retail.forecast import train as forecast
from retail.recommend import train as recommendations
from retail.snapshot import export

if __name__ == '__main__':
    prepare()
    forecast()
    recommendations()
    export()
