import json
import os
import time
from typing import Optional, Any

import pandas as pd
import streamlit as st
import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# 文件保存路径
DATA_FILE = 'projects_data.json'

# 初始化项目和数据
if 'projects' not in st.session_state:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            st.session_state.projects = {k: pd.DataFrame(v) for k, v in data.items()}
    else:
        st.session_state.projects = {}
if 'current_project' not in st.session_state:
    st.session_state.current_project = None

# 添加成功提示状态
if 'show_success' not in st.session_state:
    st.session_state.show_success = False


def load_projects():
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
        return {k: pd.DataFrame(v) for k, v in data.items()}


def save_projects(projects):
    try:
        with open(DATA_FILE, 'w') as f:
            data = {k: v.to_dict(orient='records') for k, v in projects.items()}
            json.dump(data, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存项目时出错: {str(e)}")


class ConfigKey(BaseModel):
    project: str
    key: str


class ConfigValue(BaseModel):
    value: str


class ConfigBatchUpdate(BaseModel):
    project: str
    updates: dict


class ConfigBatchDelete(BaseModel):
    project: str
    keys: list


class ConfigResponse(BaseModel):
    project: str
    key: str
    value: Optional[Any] = None


class BatchUpdateResponse(BaseModel):
    project: str
    message: str
    updated_items: int


class BatchDeleteResponse(BaseModel):
    project: str
    message: str
    deleted_items: int


async def handle_project_not_found(project_name: str):
    raise HTTPException(status_code=404, detail=f"项目 '{project_name}' 不存在")


@app.post("/config/get", response_model=ConfigResponse, summary="获取配置项")
async def get_config(config_key: ConfigKey):
    projects = load_projects()
    current_project = projects.get(config_key.project)

    if current_project is None:
        await handle_project_not_found(config_key.project)

    if config_key.key not in current_project['key'].values:
        raise HTTPException(status_code=404, detail=f"配置项 '{config_key.key}' 不存在")

    value = current_project.set_index('key').loc[config_key.key, 'value']
    return ConfigResponse(project=config_key.project, key=config_key.key, value=value)


@app.post("/config/set", response_model=ConfigResponse, summary="设置配置项")
async def set_config(config_key: ConfigKey, config_value: ConfigValue):
    projects = load_projects()
    current_project = projects.get(config_key.project)
    if current_project is None:
        await handle_project_not_found(config_key.project)
    elif current_project.empty:
        raise HTTPException(status_code=404, detail=f"配置项 '{config_key.key}' 不存在")

    config = current_project.set_index('key').to_dict()['value']
    config[config_key.key] = config_value.value

    projects[config_key.project] = pd.DataFrame(list(config.items()), columns=['key', 'value'])
    save_projects(projects)
    return ConfigResponse(project=config_key.project, key=config_key.key, value=config_value.value)


@app.delete("/config/delete", response_model=ConfigResponse, summary="删除配置项")
async def delete_config(config_key: ConfigKey):
    projects = load_projects()
    current_project = projects.get(config_key.project)
    if current_project is None:
        await handle_project_not_found(config_key.project)
    elif current_project.empty:
        raise HTTPException(status_code=404, detail=f"配置项 '{config_key.key}' 不存在")

    config = current_project.set_index('key').to_dict()['value']
    value = config.pop(config_key.key, None)

    projects[config_key.project] = pd.DataFrame(list(config.items()), columns=['key', 'value'])
    save_projects(projects)
    return ConfigResponse(project=config_key.project, key=config_key.key, value=value)


@app.post("/config/batch", response_model=BatchUpdateResponse, summary="批量设置配置项")
async def batch_set_config(batch_update: ConfigBatchUpdate):
    projects = load_projects()
    current_project = projects.get(batch_update.project)
    if current_project is None:
        await handle_project_not_found(batch_update.project)
    elif current_project.empty:
        raise HTTPException(status_code=404, detail="项目为空，无法进行批量更新")

    config = current_project.set_index('key').to_dict()['value']
    for key, value in batch_update.updates.items():
        config[key] = value

    projects[batch_update.project] = pd.DataFrame(list(config.items()), columns=['key', 'value'])
    save_projects(projects)
    return BatchUpdateResponse(project=batch_update.project, message=f"批量更新成功，共更新 {len(batch_update.updates)} 个配置项", updated_items=len(batch_update.updates))


@app.delete("/config/batch", response_model=BatchDeleteResponse, summary="批量删除配置项")
async def batch_remove_config(batch_delete: ConfigBatchDelete):
    projects = load_projects()
    current_project = projects.get(batch_delete.project)
    if current_project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    elif current_project.empty:
        raise HTTPException(status_code=404, detail="项目为空，无法进行批量删除")

    config = current_project.set_index('key').to_dict()['value']
    deleted_count = 0
    for key in batch_delete.keys:
        if key in config:
            del config[key]
            deleted_count += 1

    projects[batch_delete.project] = pd.DataFrame(list(config.items()), columns=['key', 'value'])
    save_projects(projects)
    return BatchDeleteResponse(project=batch_delete.project, message=f"批量删除成功，共删除 {deleted_count} 个配置项", deleted_items=deleted_count)


# 页面布局优化
st.set_page_config(layout="wide", page_title="配置管理平台", page_icon="⚙️")

# 主标题样式优化
st.markdown("""
    <style>
    .main-title {
        font-size: 2.5rem;
        font-weight: bold;
        color: #2d4059;
        padding: 1rem;
        border-bottom: 2px solid #2d4059;
        margin-bottom: 2rem;
    }
    </style>
    <div class="main-title">配置管理平台</div>
""", unsafe_allow_html=True)

# 显示成功提示
if st.session_state.show_success:
    st.toast("🎉 操作成功！", icon="✅")
    time.sleep(1)
    st.session_state.show_success = False

# 侧边栏 - 项目管理
with st.sidebar:
    # 侧边栏样式优化
    st.markdown("""
        <style>
        .sidebar .stHeader {
            color: #2d4059;
            font-size: 1.5rem;
            padding: 0.5rem 0;
        }
        .sidebar .stButton button {
            width: 100%;
            margin: 0.5rem 0;
        }
        </style>
    """, unsafe_allow_html=True)

    st.header("📂 项目管理")

    # 项目选择
    if st.session_state.projects:
        project_names = list(st.session_state.projects.keys())
        selected_project = st.selectbox(
            "选择项目",
            project_names,
            index=project_names.index(st.session_state.current_project) if st.session_state.current_project else 0,
            key="project_select"
        )
        if selected_project != st.session_state.current_project:
            st.session_state.current_project = selected_project
            st.rerun()

    # 项目操作
    with st.expander("🔧 项目操作", expanded=True):
        # 创建新项目部分
        st.subheader("➕ 创建新项目")
        new_project = st.text_input("新建项目名称", placeholder="输入新项目名称", key="new_project_input")
        if st.button("创建项目", use_container_width=True):
            if new_project:
                if new_project in st.session_state.projects:
                    st.error("⚠️ 项目已存在！")
                else:
                    st.session_state.projects[new_project] = pd.DataFrame(columns=['key', 'value'])
                    st.session_state.current_project = new_project
                    save_projects(st.session_state.projects)
                    st.session_state.show_success = True
                    st.rerun()
            else:
                st.warning("⚠️ 请输入项目名称")

        # 删除当前项目部分
        st.subheader("🗑️ 删除项目")
        if st.session_state.current_project:
            confirm_project = st.text_input("请输入要删除的项目名称以确认", placeholder="输入项目名称")
            if st.button("删除当前项目", use_container_width=True, type="primary"):
                if confirm_project == st.session_state.current_project:
                    del st.session_state.projects[st.session_state.current_project]
                    st.session_state.current_project = None if not st.session_state.projects else list(st.session_state.projects.keys())[0]
                    save_projects(st.session_state.projects)
                    st.session_state.show_success = True
                    st.rerun()
                else:
                    st.error("⚠️ 项目名称不匹配，删除操作已取消")
        else:
            st.warning("当前没有可删除的项目")

    # 配置操作
    if st.session_state.current_project:
        st.header("⚙️ 配置操作")
        operation = st.radio(
            "选择操作",
            ["查看配置", "添加配置", "修改配置", "删除配置", "批量操作"],
            help="选择您要执行的操作类型",
            horizontal=True
        )
        if operation == "批量操作":
            st.subheader("📁 批量操作")
            uploaded_file = st.file_uploader(
                "上传配置文件",
                type=['csv', 'json', 'yaml'],
                help="请上传包含配置项的CSV、JSON或YAML文件"
            )

            if uploaded_file is None:
                # 未上传文件时显示文件格式说明
                st.markdown("""
                **支持格式：**
                - CSV：需含key,value两列
                - JSON：键值对格式
                ```json
                {"key1":"value1","key2":"value2"}
                ```
                - YAML：键值对格式
                ```yaml
                key1: value1
                key2: value2
                ```
                """)
            else:
                try:
                    if uploaded_file.name.endswith('.csv'):
                        batch_data = pd.read_csv(uploaded_file)
                        # 检查CSV格式
                        if not {'key', 'value'}.issubset(batch_data.columns):
                            st.error("CSV文件必须包含key和value两列")
                            st.stop()
                    elif uploaded_file.name.endswith('.json'):
                        json_data = json.load(uploaded_file)
                        batch_data = pd.DataFrame(list(json_data.items()), columns=['key', 'value'])
                    elif uploaded_file.name.endswith('.yaml') or uploaded_file.name.endswith('.yml'):
                        yaml_data = yaml.safe_load(uploaded_file)
                        if not isinstance(yaml_data, dict):
                            st.error("YAML文件格式不正确，必须是键值对格式")
                            st.stop()
                        batch_data = pd.DataFrame(list(yaml_data.items()), columns=['key', 'value'])

                    # 显示预览
                    with st.expander("📄 文件内容预览"):
                        st.dataframe(batch_data.head(10))

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("➕ 批量添加", help="将文件中的配置项添加到现有配置中", use_container_width=True):
                            # 检查是否有重复key
                            # 获取现有和新的key集合
                            existing_keys = set()
                            if not st.session_state.projects[st.session_state.current_project].empty:
                                existing_keys = set(st.session_state.projects[st.session_state.current_project]['key'])
                            new_keys = set(batch_data['key'])

                            # 查找重复key
                            duplicates = existing_keys & new_keys

                            if duplicates:
                                # 显示重复key错误信息
                                st.error(f"检测到 {len(duplicates)} 个重复key，无法添加：\n{', '.join(duplicates)}")
                                st.warning("请修改文件中的重复key后重新上传")
                            else:
                                try:
                                    # 合并数据并保存
                                    updated_df = pd.concat(
                                        [st.session_state.projects[st.session_state.current_project], batch_data],
                                        ignore_index=True
                                    )
                                    st.session_state.projects[st.session_state.current_project] = updated_df
                                    save_projects(st.session_state.projects)

                                    # 显示成功提示并刷新页面
                                    st.session_state.show_success = True
                                    st.toast(f"成功添加 {len(batch_data)} 条配置项", icon="✅")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"添加配置时发生错误：{str(e)}")
                    with col2:
                        if st.button("🗑️ 批量删除", help="删除文件中存在的配置项", type="primary", use_container_width=True):
                            st.session_state.projects[st.session_state.current_project] = st.session_state.projects[st.session_state.current_project][
                                ~st.session_state.projects[st.session_state.current_project]['key'].isin(batch_data['key'])]
                            save_projects(st.session_state.projects)
                            st.session_state.show_success = True
                            st.rerun()
                except yaml.YAMLError as e:
                    st.error(f"YAML文件解析失败: {str(e)}")
                except Exception as e:
                    st.error(f"文件处理失败: {str(e)}")


def search_configs(configs: pd.DataFrame, search_term: str) -> pd.DataFrame:
    """通用搜索函数"""
    if search_term:
        return configs[configs['key'].str.contains(search_term, case=False)]
    return configs


def get_paginated_data(configs: pd.DataFrame, page: int, page_size: int = 10) -> pd.DataFrame:
    """分页处理函数"""
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    return configs.iloc[start_idx:end_idx]


# 主界面
if st.session_state.current_project:
    current_configs = st.session_state.projects[st.session_state.current_project]

    if operation == "查看配置":
        st.subheader(f"📂 当前项目: {st.session_state.current_project}")
        if len(current_configs) > 0:
            search_term = st.text_input("🔍 搜索配置项", placeholder="输入关键字过滤配置项")

            # 使用通用搜索函数
            filtered_configs = search_configs(current_configs, search_term)

            # 分页处理
            page_size = 10
            total_pages = (len(filtered_configs) + page_size - 1) // page_size
            page = st.number_input("📄 页码", min_value=1, max_value=total_pages, value=1)
            paginated_configs = get_paginated_data(filtered_configs, page, page_size)

            # 显示配置项
            with st.container():
                for _, row in paginated_configs.iterrows():
                    with st.expander(f"🔑 {row['key']}"):
                        st.markdown(f"**配置值:**\n{row['value']}")
                        st.markdown("---")

                st.caption(f"📊 显示 {len(paginated_configs)} 条配置项（共 {len(filtered_configs)} 条）")

                if st.button("📋 复制所有配置项"):
                    config_text = "\n".join([f"{row['key']}: {row['value']}" for _, row in filtered_configs.iterrows()])
                    st.session_state.copied_config = config_text
                    st.toast("配置项已复制到剪贴板", icon="📋")
        else:
            st.info("ℹ️ 当前项目暂无配置项，请添加配置")

    elif operation == "添加配置":
        st.subheader("➕ 添加新配置")
        search_term = st.text_input("🔍 搜索配置项", placeholder="输入关键字搜索已有配置", key="add_search")

        # 使用通用搜索函数
        matched_keys = search_configs(current_configs, search_term).get('key', pd.Series(dtype='object'))
        if search_term and len(matched_keys) > 0:
            st.info(f"🔍 找到以下相关配置项：{', '.join(matched_keys)}")

        with st.form("add_config"):
            key = st.text_input("配置项", placeholder="请输入配置项名称", key="add_key")
            value = st.text_input("配置值", placeholder="请输入配置值", key="add_value")

            if st.form_submit_button("添加", use_container_width=True):
                if key and value:
                    if key in current_configs['key'].values:
                        st.error("⚠️ 该配置项已存在！")
                    else:
                        new_row = pd.DataFrame({'key': [key], 'value': [value]})
                        st.session_state.projects[st.session_state.current_project] = pd.concat(
                            [current_configs, new_row], ignore_index=True)
                        save_projects(st.session_state.projects)
                        st.session_state.show_success = True
                        st.rerun()
                else:
                    st.warning("⚠️ 请填写完整的配置项和配置值")

    elif operation == "修改配置":
        st.subheader("✏️ 修改配置")
        if len(current_configs) > 0:
            search_term = st.text_input("搜索配置项", placeholder="输入关键字搜索", key="edit_search")

            # 使用通用搜索函数
            filtered_keys = search_configs(current_configs, search_term)['key']

            if len(filtered_keys) > 0:
                selected_key = st.selectbox("选择要修改的配置项", filtered_keys,
                                            help="请选择要修改的配置项", key="edit_select")
                selected_row = current_configs[current_configs['key'] == selected_key]
                with st.form("edit_config"):
                    new_value = st.text_input("新配置值", value=selected_row.iloc[0]['value'],
                                              placeholder="请输入新的配置值", key="edit_value")
                    if st.form_submit_button("更新", use_container_width=True):
                        st.session_state.projects[st.session_state.current_project].loc[
                            current_configs['key'] == selected_key, 'value'] = new_value
                        save_projects(st.session_state.projects)
                        st.session_state.show_success = True
                        st.rerun()
            else:
                st.warning("⚠️ 未找到匹配的配置项")
        else:
            st.info("ℹ️ 当前项目暂无配置项，请先添加配置")

    elif operation == "删除配置":
        st.subheader("🗑️ 删除配置")
        if len(current_configs) > 0:
            search_term = st.text_input("搜索配置项", placeholder="输入关键字搜索", key="delete_search")

            # 使用通用搜索函数
            filtered_keys = search_configs(current_configs, search_term)['key']

            if len(filtered_keys) > 0:
                selected_key = st.selectbox("选择要删除的配置项", filtered_keys,
                                            help="请选择要删除的配置项", key="delete_select")
                if st.button("删除", use_container_width=True, type="primary"):
                    st.session_state.projects[st.session_state.current_project] = current_configs[
                        current_configs['key'] != selected_key]
                    save_projects(st.session_state.projects)
                    st.session_state.show_success = True
                    st.rerun()
            else:
                st.warning("⚠️ 未找到匹配的配置项")
        else:
            st.info("ℹ️ 当前项目暂无配置项，请先添加配置")
else:
    st.info("ℹ️ 请先创建或选择一个项目")
