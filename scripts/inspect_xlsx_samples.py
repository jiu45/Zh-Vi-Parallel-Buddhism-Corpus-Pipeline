import sys, openpyxl
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

wb = openpyxl.load_workbook(r'd:\CS\NLP\Mid-Term\CV09_AQPSVS_Q3\04_dong_hang\AQPSVS_Q3_parallel.xlsx')
ws = wb['DONG_HANG']
print('Excel Title:', ws.title)
print('Total Rows:', ws.max_row)
print('Header:', ws.cell(row=1, column=1).value, '|', ws.cell(row=1, column=2).value)

sample_rows = [2, 10, 27, 45, 70, 100, 140, ws.max_row]
for r in sample_rows:
    h = ws.cell(row=r, column=1).value
    v = ws.cell(row=r, column=2).value
    print(f'\n--- Row {r} ---')
    print('Hán :', h[:70] + ('...' if len(h)>70 else ''))
    print('Việt:', v[:70] + ('...' if len(v)>70 else ''))
