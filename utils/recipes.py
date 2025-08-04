import logging
import pandas as pd
import xlwings as xw
import sys
import os

# 添加父目录到Python路径
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from core.generator import (
    load_data,
    prepare_template,
    generate_one_archive_directory,
    get_subset,
    cleanup_stream,
)

# --- 应用层：功能配方 ---


def create_qy_full_index(
    jn_catalog_path,
    aj_catalog_path,
    template_path,
    output_folder,
    start_file="",
    end_file="",
):
    """
    配方：生成传统文书全引目录。
    """
    logging.info("--- 开始生成传统文书全引目录 ---")
    jn_data = load_data(jn_catalog_path)
    aj_data = load_data(aj_catalog_path)
    template_stream = prepare_template(template_path)

    if jn_data is None or template_stream is None:
        logging.error("卷内数据或模板加载失败，任务终止。")
        return
    if aj_data is None:
        logging.warning("案卷数据加载失败，将无法填充案卷的静态信息。")

    # 定义"全引目录"的特定配置
    ARCHIVE_ID_COLUMN = "案卷档号"
    unique_archive_ids = jn_data[ARCHIVE_ID_COLUMN].unique()

    # 列映射: {目标模板列号: 源数据列名}
    column_mapping = {
        1: "件号",
        2: "责任者",
        3: "文号",
        4: "题名",
        5: "文件时间",
        6: "起页号",
        7: "备注",
    }
    # 需要自适应字体大小的列号
    autofit_columns = [2, 4, 7]  # 责任者, 题名, 备注

    logging.info(f"共找到 {len(unique_archive_ids)} 个独立案卷。")

    with xw.App(visible=False) as app:
        # 创建一个用于计算的临时单元格对象
        rng = app.books[0].sheets[0].range("A1")
        rng.font.name = "宋体"
        rng.font.size = 11

        subset_ids = get_subset(unique_archive_ids, start_file, end_file)
        total_pages = 0

        for i, archive_id in enumerate(subset_ids, start=1):
            # 筛选当前案卷的数据
            current_archive_jn_data = jn_data[jn_data[ARCHIVE_ID_COLUMN] == archive_id]

            static_cells = {}
            if aj_data is not None:
                current_archive_aj_data_rows = aj_data[
                    aj_data[ARCHIVE_ID_COLUMN] == archive_id
                ]
                if not current_archive_aj_data_rows.empty:
                    current_archive_aj_data = current_archive_aj_data_rows.iloc[0]
                    # 准备静态单元格信息
                    static_cells = {
                        "C2": current_archive_aj_data.get("全宗号"),
                        "D2": current_archive_aj_data.get("目录号"),
                        "E2": current_archive_aj_data.get("案卷号"),
                        "F2": current_archive_aj_data.get("年度"),
                        "G2": current_archive_aj_data.get("保管期限"),
                        "H2": current_archive_aj_data.get("归档号"),
                        "J1": current_archive_aj_data.get("案卷题名"),
                    }
                else:
                    logging.warning(f"在案卷目录中未找到档号为 {archive_id} 的信息。")

            total_pages += generate_one_archive_directory(
                archive_data=current_archive_jn_data,
                template_stream=template_stream,
                output_folder=output_folder,
                archive_id=archive_id,
                rng_for_calc=rng,
                index=i,
                column_mapping=column_mapping,
                autofit_columns=autofit_columns,
                static_cells=static_cells,
                title_row_num=3,  # "全引目录"的标题有3行
            )

    logging.info(f"--- 生成结束 ---")
    logging.info(f"总计处理了 {len(subset_ids)} 件案卷, 共生成 {total_pages} 页。")
    cleanup_stream(template_stream)


def create_aj_index(
    catalog_path, template_path, output_folder, start_file="", end_file=""
):
    """配方：生成案卷目录。"""
    logging.info("--- 开始生成案卷目录 ---")
    data = load_data(catalog_path)
    template_stream = prepare_template(template_path)

    if data is None or template_stream is None:
        logging.error("数据或模板加载失败，任务终止。")
        return

    # 定义"案卷目录"的特定配置
    ARCHIVE_ID_COLUMN = "案卷号"  # 使用案卷号作为唯一标识
    unique_archive_ids_all = data[ARCHIVE_ID_COLUMN].unique()
    unique_archive_ids = get_subset(unique_archive_ids_all, start_file, end_file)

    # 列映射: {目标模板列号: 源数据列名}
    column_mapping = {
        1: "案卷号",
        2: "案卷题名",
        3: "起始年度",
        4: "终止年度",
        5: "保管期限",
        6: "件数",
        7: "页数",
        8: "备注",
    }
    # 需要自适应字体大小的列号
    autofit_columns = [2, 8]  # 案卷题名, 备注

    # 静态信息
    static_cells = {
        "B3": data.iloc[0].get("全宗号"),
        "C3": data.iloc[0].get("目录号"),
    }

    logging.info(f"共找到 {len(unique_archive_ids)} 个独立案卷。")

    # 筛选出需要处理的数据行
    filtered_data = data[data[ARCHIVE_ID_COLUMN].isin(unique_archive_ids)]

    with xw.App(visible=False) as app:
        rng = app.books[0].sheets[0].range("A1")
        rng.font.name = "宋体"
        rng.font.size = 11

        total_pages = generate_one_archive_directory(
            archive_data=filtered_data,
            template_stream=template_stream,
            output_folder=output_folder,
            archive_id=f"案卷目录_{start_file}-{end_file}",
            rng_for_calc=rng,
            index=1,
            column_mapping=column_mapping,
            autofit_columns=autofit_columns,
            static_cells=static_cells,
            title_row_num=4,
        )

    logging.info(f"--- 生成结束 ---")
    logging.info(
        f"总计处理了 {len(unique_archive_ids)} 条记录, 共生成 {total_pages} 页。"
    )
    cleanup_stream(template_stream)


def create_jn_or_jh_index(
    catalog_path,
    template_path,
    output_folder,
    recipe_name,
    start_file="",
    end_file="",
):
    """配方：生成卷内目录 或 简化目录。"""
    logging.info(f"--- 开始生成 {recipe_name} ---")
    data = load_data(catalog_path)
    template_stream = prepare_template(template_path)

    if data is None or template_stream is None:
        logging.error("数据或模板加载失败，任务终止。")
        return

    ARCHIVE_ID_COLUMN = "案卷档号"
    all_ids = data[ARCHIVE_ID_COLUMN].unique()
    subset_ids = get_subset(all_ids, start_file, end_file)
    subset_data = data[data[ARCHIVE_ID_COLUMN].isin(subset_ids)]

    # 根据配方名称定义不同的列映射
    if recipe_name == "卷内目录":
        column_mapping = {
            1: "顺序号",
            2: "文号",
            3: "责任者",
            4: "题名",
            5: "文件时间",
            6: "页号",
            7: "备注",
        }
        autofit_columns = [2, 3, 4]  # 题名, 备注
    elif recipe_name == "简化目录":
        column_mapping = {
            1: "顺序号",
            2: "档号",
            3: "题名",
            4: "页数",
        }
        autofit_columns = [3]  # 题名
    else:
        logging.error(f"未知的配方名称: {recipe_name}")
        return

    logging.info(f"共找到 {len(subset_ids)}卷,{len(subset_data)} 条记录。")

    with xw.App(visible=False) as app:
        rng = app.books[0].sheets[0].range("A1")
        rng.font.name = "宋体"
        rng.font.size = 11

        for index, id in enumerate(subset_ids, start=1):
            data = subset_data[subset_data[ARCHIVE_ID_COLUMN] == id]
            total_pages = generate_one_archive_directory(
                archive_data=data,
                template_stream=template_stream,
                output_folder=output_folder,
                archive_id=f"{recipe_name}_{id}",
                rng_for_calc=rng,
                index=index,
                column_mapping=column_mapping,
                autofit_columns=autofit_columns,
                title_row_num=4,
            )

    logging.info(f"--- 生成结束 ---")
    logging.info(
        f"总计处理了{len(subset_ids)}卷， {len(subset_data)} 条记录, 共生成 {total_pages} 页。"
    )
    cleanup_stream(template_stream)
