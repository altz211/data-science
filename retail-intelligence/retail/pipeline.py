from retail.prepare import prepare
from retail.forecast import train as forecast
from retail.recommend import train as recommendations
from retail.snapshot import export
from retail.kpis import export as export_kpis

if __name__ == '__main__':
    prepare()
    forecast()
    recommendations()
    export()
    export_kpis()
