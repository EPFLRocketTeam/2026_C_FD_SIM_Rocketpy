import Excel.excel_io as xl

dfs = xl.dfs_from_excel("2026_prop_budget.xlsx")
a = xl.Input.from_dfs(dfs,16)
a.display()