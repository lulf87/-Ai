# 预置法规来源核对清单

核对日期：2026-05-15

本清单只记录预置法规库的来源状态。法规内容是否适用于具体产品注册路径，仍需人工确认。

| 预置法规 | 文号/来源 | 官方链接状态 | 附件 SHA 状态 | 当前校验状态 |
| --- | --- | --- | --- | --- |
| 医疗器械监督管理条例 | 国务院令第739号，根据国务院令第797号第二次修订；司法部行政法规库 LawID=1739 | NMPA 旧页在浏览器中显示“网站地址已变更”，已改用司法部国家行政法规库官方条目：`https://xzfg.moj.gov.cn/law/detail?LawID=1739` | 已通过浏览器下载司法部官方 Word；SHA 已计算并导入当前库 | 待人工确认校验 |
| 医疗器械注册与备案管理办法 | 国家市场监督管理总局令第47号 | 已更新为 SAMR 官方规章页：`https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/fgs/art/2023/art_568880e3ee344c45b38d073bba1c53ad.html` | 无附件文件 SHA | 待校验 |
| 医疗器械注册申报资料要求和批准证明文件格式 | 国家药监局 2021年第121号 | 已更新为 NMPA 医疗器械公告页：`https://www.nmpa.gov.cn/xxgk/ggtg/ylqxggtg/ylqxqtggtg/20210930155134148.html` | 已导入公告页列出的 9 个 NMPA 官方 `.doc` 附件 | 待人工确认校验 |
| 医疗器械产品技术要求编写指导原则 | 国家药监局 2022年第8号 | 已更新为 NMPA 医疗器械公告页：`https://www.nmpa.gov.cn/ylqx/ylqxggtg/20220209152322130.html` | 已导入 NMPA 官方 `.doc` 附件 | 待人工确认校验 |
| 医疗器械临床评价技术指导原则等5项技术指导原则 | 国家药监局 2021年第73号 | NMPA 医疗器械公告页：`https://www.nmpa.gov.cn/ylqx/ylqxggtg/20210928170338138.html` | 已通过浏览器补齐 5 个 NMPA 官方 `.docx` 附件，替代原转载附件作为可校验来源 | 待人工确认校验 |
| 医疗器械软件注册审查指导原则（2022年修订版） | 国家药监局器审中心通告 2022年第9号 | CMDE 指导原则页：`https://www.cmde.org.cn/flfg/zdyz/zdyzwbk/20220309091706965.html` | 已通过浏览器从页面附件入口下载 CMDE 官方 `.docx` 附件 | 待人工确认校验 |
| 医疗器械网络安全注册审查指导原则（2022年修订版） | 国家药监局器审中心通告 2022年第7号 | CMDE 指导原则页：`https://www.cmde.org.cn/flfg/zdyz/zdyzwbk/20220309085900737.html` | 已通过浏览器从页面附件入口下载 CMDE 官方 `.docx` 附件 | 待人工确认校验 |
| 人工智能医疗器械注册审查指导原则 | 国家药监局器审中心通告 2022年第8号 | CMDE 指导原则页：`https://www.cmde.org.cn/flfg/zdyz/zdyzwbk/20220309091014461.html` | 已通过浏览器从页面附件入口下载 CMDE 官方 `.docx` 附件 | 待人工确认校验 |
| 有源医疗器械使用期限注册技术审查指导原则 | 国家药监局器审中心通告 2019年第23号 | CMDE 指导原则页：`https://www.cmde.org.cn/flfg/zdyz/fbg/fbgyy/20190515101100823.html` | 页面列出的附件链接实际跳转到 NMPA 首页，浏览器未产生下载文件；仍未校验 | 待补官方附件 |
| 医疗器械说明书和标签管理规定 | 国家食品药品监督管理总局令第6号 | NMPA 医疗器械部门规章页：`https://www.nmpa.gov.cn/ylqx/ylqxfgwj/ylqxbmgzh/20140730180001248.html` | 无单独附件；已通过浏览器保存渲染 HTML 快照并导入正文，SHA 已计算 | 待人工确认校验 |

## 处理原则

- 只有官方链接和至少一个已下载/已上传、已计算 SHA 且已抽取正文的可校验来源同时满足时，前端才允许点击“确认校验”。有官方附件的公告优先使用附件；无附件且网页本身为法规正文的条目使用官方网页正文快照。
- 非 NMPA/CMDE/SAMR 官方直连附件只作为参考 SHA 展示，不作为自动校验条件。
- 预置法规默认不直接作为规则依据；只有人工确认校验后的法规才会被规则命中项引用。

## 本次已核对的官方附件 SHA

以下 SHA 均来自本地浏览器实际下载或浏览器渲染快照；浏览器无法下载的 `有源医疗器械使用期限注册技术审查指导原则` 未列为可校验来源。

| 预置法规 | 文件 | 官方来源 URL | SHA256 |
| --- | --- | --- | --- |
| 医疗器械监督管理条例 | 医疗器械监督管理条例-司法部行政法规库.docx | `https://xzfg.moj.gov.cn/law/download?LawID=1739&type=word` | `c96a78eadb0019f15591b91a66ccff3c8a7f5dd5cc949040d2f21ee6e879a051` |
| 医疗器械临床评价技术指导原则等5项技术指导原则 | 国家药品监督管理局2021年第73号通告附件1.docx | `https://www.nmpa.gov.cn/directory/web/nmpa/images/1632819763420054609.docx` | `d1e3e10c56c95180f6bcf3835b4d801e437f9d9c97d957e7539926bcc4c7cd93` |
| 医疗器械临床评价技术指导原则等5项技术指导原则 | 国家药品监督管理局2021年第73号通告附件2.docx | `https://www.nmpa.gov.cn/directory/web/nmpa/images/1632819776867038341.docx` | `e29822baa40a9fc813001309148234557a73bf202fb0bcd3c9cb16dbd5489853` |
| 医疗器械临床评价技术指导原则等5项技术指导原则 | 国家药品监督管理局2021年第73号通告附件3.docx | `https://www.nmpa.gov.cn/directory/web/nmpa/images/1632819786391052048.docx` | `af61cae41a5bacda2d1e9b3df0f5664b1d2c05c8a96772527d018a8242dfb3cf` |
| 医疗器械临床评价技术指导原则等5项技术指导原则 | 国家药品监督管理局2021年第73号通告附件4.docx | `https://www.nmpa.gov.cn/directory/web/nmpa/images/1737100251012055245.docx` | `8ac844fe779c820987b18b06a4ef9ec55f494d7fc35204cb51da070dd46802ce` |
| 医疗器械临床评价技术指导原则等5项技术指导原则 | 国家药品监督管理局2021年第73号通告附件5.docx | `https://www.nmpa.gov.cn/directory/web/nmpa/images/1632819808082069085.docx` | `cbabbf48ce91da76064f196ef1d1b8b7917bc9e1cd95cbe4ea2703ec42fd597b` |
| 医疗器械软件注册审查指导原则（2022年修订版） | 医疗器械软件注册审查指导原则（2022年修订版）.docx | `https://www.cmde.org.cn/directory/web/cmde/images/0r3Bxsb30LXI7bz+16Ky4cnzsunWuLW81K3U8qOoMjAyMsTq0N62qbDmo6mjqDIwMjLE6rXaObrFo6kuZG9jeA==.docx` | `4526e98203bb0bd11771b1ea24d84d0d887191dc5463e16bd2d8708dff97943a` |
| 医疗器械网络安全注册审查指导原则（2022年修订版） | 医疗器械网络安全注册审查指导原则（2022年修订版）.docx | `https://www.cmde.org.cn/directory/web/cmde/images/0r3Bxsb30LXN+MLnsLLIq9eisuHJ87Lp1ri1vNSt1PKjqDIwMjLE6tDetqmw5qOpo6gyMDIyxOq12je6xaOpLmRvY3g=.docx` | `0c86ba0c14cdd4451441749b9b482801bb256458c516651920be48d1c70fc536` |
| 人工智能医疗器械注册审查指导原则 | 人工智能医疗器械注册审查指导原则（2022年第8号）.docx | `https://www.cmde.org.cn/directory/web/cmde/images/yMu5pNbHxNzSvcHGxvfQtdeisuHJ87Lp1ri1vNSt1PKjqDIwMjLE6rXaOLrFo6kuZG9jeA==.docx` | `eb048e49669624a925c6530e2bce5fdc72891678db2eadddf7575b3ed050bc02` |
| 医疗器械说明书和标签管理规定 | 医疗器械说明书和标签管理规定-浏览器渲染.html | `https://www.nmpa.gov.cn/ylqx/ylqxfgwj/ylqxbmgzh/20140730180001248.html` | `c95000c8cec6d1291e0e1e85d6a4b51502b521f5a5d3aa3cbfac8df4bf9a29b2` |

`医疗器械注册申报资料要求和批准证明文件格式`（国家药监局 2021年第121号）的 9 个附件均来自 NMPA 官方公告页附件链接：

| 附件 | 官方附件 URL | SHA256 |
| --- | --- | --- |
| 附件1 | `https://www.nmpa.gov.cn/directory/web/nmpa/images/1632988186580021650.doc` | `d359740df90da956064b219334fccf5e45d644c460960ab59faf2d3fe816ea99` |
| 附件2 | `https://www.nmpa.gov.cn/directory/web/nmpa/images/1632988205304086795.doc` | `b31163fd2bc270f2ce81ffc6f5ff82d79987e52cf90c367d544fa0b0202d96b2` |
| 附件3 | `https://www.nmpa.gov.cn/directory/web/nmpa/images/1632988221783066176.doc` | `057f0cd727ad38a25640a0a77403ffe5849931b2f6cee6f7817ce27657f6a851` |
| 附件4 | `https://www.nmpa.gov.cn/directory/web/nmpa/images/1632988231710093747.doc` | `918de55c070b86dfbcae6d013dcf2ce8afbc1fedd5a1aa84e2c2962ba842c5db` |
| 附件5 | `https://www.nmpa.gov.cn/directory/web/nmpa/images/1634282952197097025.doc` | `9cec3ef722dfe4c9b4f4b7caf1e3d208ac4ba8c6bdca67bf22a01c934b33fee5` |
| 附件6 | `https://www.nmpa.gov.cn/directory/web/nmpa/images/1632988250494049947.doc` | `5ae48ce57199d1ae6f69c539f0fc2b44d5d783361c9b20c211fd76ba8692070c` |
| 附件7 | `https://www.nmpa.gov.cn/directory/web/nmpa/images/1632988263501098716.doc` | `b00c4e70ec266a5764e114b131d13995b3fd0a3546522beb566ca51110556341` |
| 附件8 | `https://www.nmpa.gov.cn/directory/web/nmpa/images/1632988272729021886.doc` | `09fec8fe889b85590e9984b71d39e44a512585b338b61b89f56ed9e5b335a6fc` |
| 附件9 | `https://www.nmpa.gov.cn/directory/web/nmpa/images/1632988285420086318.doc` | `84f97d0fb9a587d4d1dfbc22da619b8616eac3907ab2999ce33d66739d081292` |
