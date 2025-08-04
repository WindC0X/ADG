import win32com.client as win32
import os


def xlsx2xls(file_path):
    try:
        Excelapp = win32.gencache.EnsureDispatch("Excel.Application")
        workbook = Excelapp.Workbooks.Open(file_path)
        new_path = file_path.replace("xlsx", "xls")
        workbook.SaveAs(new_path, FileFormat=56)
        workbook.Close()
    except Exception as e:
        print("转换 .xlsx 为 .xls 时出错:", e)
    finally:
        Excelapp.Application.Quit()


def xls2xlsx(file_path):
    try:
        Excelapp = win32.gencache.EnsureDispatch("Excel.Application")
        workbook = Excelapp.Workbooks.Open(file_path)
        new_path = file_path.replace("xls", "xlsx")
        workbook.SaveAs(new_path, FileFormat=51)
        workbook.Close()
    except Exception as e:
        print("转换 .xls 为 .xlsx 时出错:", e)
    finally:
        Excelapp.Application.Quit()


if __name__ == "__main__":

    file_path = r"path/to/your/excel/file.xlsx"
    folder_path = r"E:\Document\明溪\胡坊镇\控制使用\卷内目录"
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if not os.path.exists(file_path):
            raise FileNotFoundError("文件路径不存在:", file_path)

    xlsx2xls(file_path)  # 调用函数并进行转换
