# Your first document workspace / 第一个文档工作区

These two short text files are fictional, reusable demo material. They contain no
real customer data, credentials or personal contact details. The README screenshots
were captured using these files in a real local Lumidoc deployment.

这两份短文本是虚构的演示资料，不含真实客户数据、凭据或私人联系方式。
仓库首页截图来自实际部署，使用的就是这些文件。

## English walkthrough

Start Lumidoc using the [quick start](../../README.md#quick-start), then open
`http://localhost:3000`. Create your own account; there is no shared demo password.

1. **Create a project.** Name it `Harbor Studio launch`. Enter its workspace.
2. **Upload both files.** Open Document Analysis and select [launch-brief.txt](./launch-brief.txt)
   and [support-guide.txt](./support-guide.txt). Both should reach Completed.
3. **Inspect the extraction.** Select a document, then Preview or Download. The
   processed text should include the names and dates from the original file.
4. **Import into the knowledge base.** Open Knowledge Graph, select both files,
   and choose Import selected files. Wait for Processed before asking about them.
5. **Ask a question.** Open Chat and ask one of the questions below. Check the
   answer against the document; small local models can make mistakes.
6. **Continue the conversation.** Ask a follow-up without creating another chat.
   Reload the page or return through the sidebar to see the same conversation.

| Question | Facts to check in the source |
| --- | --- |
| Who owns the launch, and when is the rehearsal? | Maya Chen; 8 April 2027. |
| What must be ready before launch? | Test the booking flow; publish cancellation/contact information; approve the support guide and coverage. |
| Who handles an outage? | Sam records it and contacts Leo; Maya decides whether the launch must be delayed. |
| What is the cancellation policy? | No fee up to 24 hours before the booking; later requests are reviewed individually. |

To explore cleanup, remove one document from the knowledge base. Its original
remains in Documents and can be imported again. Deleting a source file and removing
its knowledge-base index are separate actions.

## 中文操作步骤

按照[快速开始](../../README.zh-CN.md#快速开始)启动后，打开 `http://localhost:3000`，
注册自己的账户。没有需要共享的演示密码。顶部语言菜单可切换中文，并记住选择。

1. 创建 `Harbor Studio launch` 项目，进入项目工作区。
2. 在文档页面同时上传本目录的两个 `.txt` 文件，等待处理完成。
3. 选择文档，预览或下载处理后的文本，核对名字和日期。
4. 打开知识库，勾选两份文件并导入，等待状态变为已处理。
5. 在聊天中问“谁负责发布？演练日期是哪一天？”，核对 **Maya Chen**、**2027 年 4 月 8 日**。
6. 继续问“发布前要完成哪些检查？”，保留在同一个会话中。刷新或从侧栏返回后，历史仍然存在。

从知识库删除文档只移除索引，原始文件仍在文档列表中，可再次导入。
删除源文件与移除知识库索引是两个独立操作。

## If something is still waiting / 如果一直在等待

| What you see / 现象 | What to check / 检查方法 |
| --- | --- |
| First startup is slow / 首次启动慢 | Model and image downloads need network access; watch the startup terminal. / 查看启动终端中的镜像和模型下载进度。 |
| Document is processing / 文档处理中 | Wait for extraction before importing. OCR takes longer than these plain-text examples. / 先完成文本提取；扫描件 OCR 比示例文本耗时更长。 |
| Uploaded file is not searchable / 上传后检索不到 | Import it into the same project's knowledge base. / 还需导入同一个项目的知识库。 |
| Answer is slow / 回复慢 | CPU inference and the first model load can take longer. Check the selected model and runtime. / 检查所选模型及运行方式；CPU 和首次加载通常更慢。 |
| Recovering / 正在恢复 | Accepted work retries after service recovery; an abandoned worker lease may take 60–90 seconds to expire. / 已接受的任务会重试，旧进程租约可能需等待 60–90 秒。 |

For a reproducible bug, use the [issue template](https://github.com/YiwenLu-yiwen/Lumidoc/issues/new/choose)
and these sample files rather than uploading private documents to a public issue.
