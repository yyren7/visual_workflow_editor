import PyPDF2
import os

def extract_text_from_pdf(pdf_path):
    print(f"开始处理 PDF 文件: {pdf_path}", flush=True)
    try:
        if not os.path.exists(pdf_path):
            print(f"错误: PDF 文件未找到于路径 {pdf_path}", flush=True)
            return None

        output_directory = os.path.dirname(pdf_path)
        base_name = os.path.basename(pdf_path)
        output_filename = os.path.splitext(base_name)[0] + ".txt"
        output_path = os.path.join(output_directory, output_filename)
        print(f"准备将文本保存到: {output_path}", flush=True)

        text_content = ""
        with open(pdf_path, 'rb') as file:
            print(f"成功打开 PDF 文件: {pdf_path}", flush=True)
            reader = PyPDF2.PdfReader(file)
            num_pages = len(reader.pages)
            print(f"PDF共有 {num_pages} 页。", flush=True)
            for page_num in range(num_pages):
                page = reader.pages[page_num]
                extracted_page_text = page.extract_text()
                if extracted_page_text:
                    text_content += extracted_page_text + "\n" # 添加换行符以分隔每页内容
                    print(f"从第 {page_num + 1} 页提取了 {len(extracted_page_text)} 字符的文本。", flush=True)
                else:
                    print(f"第 {page_num + 1} 页没有提取到文本或提取内容为空。", flush=True)
        
        if not text_content.strip(): # 检查提取的内容是否为空或仅包含空白字符
            print("未能从PDF中提取任何有效文本内容。", flush=True)
            return None

        print(f"总共提取文本长度 (包括换行符): {len(text_content)} 字符。", flush=True)
        with open(output_path, 'w', encoding='utf-8') as outfile:
            outfile.write(text_content)
        
        print(f"文本已成功提取并保存到: {output_path}", flush=True)
        return output_path
    except FileNotFoundError: # 理论上已被 os.path.exists 覆盖，但保留
        print(f"错误: 文件未找到 {pdf_path}", flush=True)
        return None
    except Exception as e:
        import traceback
        print(f"提取文本时发生未预料的错误: {e}", flush=True)
        print(traceback.format_exc(), flush=True)
        return None

if __name__ == "__main__":
    pdf_file_path = "database/prompt_database/node_description/ブロック説明 - ncpt-am Documents.pdf"
    print(f"脚本开始执行，目标 PDF: {pdf_file_path}", flush=True)
    
    if not os.path.exists(pdf_file_path):
        print(f"在 __main__ 中检查: PDF 文件 {pdf_file_path} 不存在。请检查路径。", flush=True)
    else:
        print(f"在 __main__ 中检查: PDF 文件 {pdf_file_path} 已找到。", flush=True)

    extracted_file_path = extract_text_from_pdf(pdf_file_path)
    if extracted_file_path:
        print(f"操作完成。文本文件已保存至: {extracted_file_path}", flush=True)
    else:
        print("操作失败，未能提取或保存文本。", flush=True) 