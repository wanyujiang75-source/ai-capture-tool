import Foundation

enum BreakpointCopy {
    static let title = "断点"
    static let close = "关闭面板"
    static let globalHelp = "待处理队列不受接口搜索、过滤、清空或历史选择影响。"
    static let chooseCapture = "选择正在录制的抓包"
    static let refresh = "刷新断点状态"
    static let processing = "正在处理断点…"
    static let waiting = "等待处理"
    static let selectPending = "选择一个待处理断点查看并修改内容。"
    static let ruleURL = "完整接口地址（不保存查询参数）"
    static let newRule = "新建规则"
    static let templates = "复用已保存规则"
    static let templateFailed = "规则已保存到本次抓包，但本机模板保存失败。下次需重新添加。"
    static let once = "仅下一次"
    static let continuous = "持续拦截"
    static let consumed = "已命中一次"
    static let ruleEnabled = "规则已启用"
    static let ruleDisabled = "规则已停用"
    static let editRule = "编辑规则"
    static let disableRule = "停用规则"
    static let enableRule = "启用规则"
    static let method = "方法"
    static let stageLabel = "暂停阶段"
    static let match = "路径匹配"
    static let exact = "精确路径"
    static let prefix = "路径前缀"
    static let path = "路径"
    static let timeout = "等待时限"
    static let cancel = "取消编辑"
    static let saveRule = "保存规则"
    static let saveEnable = "保存并启用断点"
    static let formatJSON = "格式化 JSON"
    static let abortWarning = "终止只结束本次连接，不会撤销服务器已执行的操作，也不会自动重试。"
    static let url = "URL"
    static let status = "响应状态码"
    static let headers = "请求头 / 响应头"
    static let addHeader = "添加请求头"
    static let body = "正文"
    static let headerName = "名称"
    static let headerValue = "值"
    static let hidden = "已隐藏，显示后可编辑"
    static let removeHeader = "删除行"
    static let backToEdit = "返回编辑"
    static let archive = "断点修改记录"
    static let archiveHelp = "生效内容表示代理采用的内容，不代表对端已收到或服务器已成功执行。"
    static let archiveTruncated = "正文仅展示前 32 KiB，完整内容保留在抓包归档中。"
    static let archiveUnavailable = "此版本正文暂时无法预览。"
    static func auditAction(_ action: String, adopted: Bool) -> String {
        switch action {
        case "apply": adopted ? "修改已被代理采用" : "修改未被代理采用"
        case "abort": "本次请求已终止"
        default: "本阶段保留原始内容"
        }
    }
    static let rules = "断点规则"
    static let setRule = "设置断点"
    static let enable = "启用断点"
    static let disable = "关闭断点"
    static let empty = "暂无待处理断点。启用规则后，请在应用中重新触发接口。"
    static let unavailable = "当前抓包不支持断点。请使用新版工具开始一次新的抓包。"
    static let noCapture = "尚无正在录制的抓包，请先开始抓包。"
    static let ended = "此断点已结束，不能再修改。请重新触发接口。"
    static let accepted = "操作已受理，正在继续转发。是否送达请查看接口结果。"
    static let abortAccepted = "终止操作已受理。连接结果请查看接口记录。"
    static let disconnected = "断点连接中断，暂停项将按超时机制原样放行。请刷新断点状态。"
    static let original = "保留原始内容并继续"
    static let apply = "应用修改并继续"
    static let abort = "终止本次请求"
    static let release = "全部保留原始内容并继续"
    static let releaseHelp = "将关闭断点并丢弃未应用的草稿，抓包继续运行。"
    static let limited = "此正文为流式、二进制或超过编辑上限，本次不支持正文修改。"
    static let loading = "正在获取断点状态…"
    static let draft = "修改内容"
    static let before = "原始内容"
    static let after = "生效内容"
    static let review = "对照修改"
    static let showSecrets = "显示敏感请求头"
    static let reuse = "规则只绑定当前抓包，切换设备或重启后不会自动启用。"
    static func queue(_ count: Int) -> String { "待处理 \(count)" }
    static func stage(_ stage: String) -> String {
        switch stage { case "request": "发送请求前"; case "response": "返回响应前"; default: "请求和响应" }
    }
    static func paused(_ stage: String) -> String {
        stage == "request" ? "请求已暂停，尚未发送到服务器。" : "响应已暂停，尚未返回应用。服务器已执行本次请求。"
    }
    static func countdown(_ seconds: Int) -> String { "剩余 \(seconds) 秒；超时后将保留原始内容并继续。" }
    static func issue(_ error: Error) -> String {
        switch (error as? BreakpointFailure)?.code {
        case "stage_ended", "capture_ended", "capture_not_found", "target_conflict", "revision_conflict": ended
        case "invalid_json": "JSON 格式不正确，请修正后再继续。"
        case "body_limit": limited
        case "origin_change": "只能修改当前站点的路径与参数，不能更换协议、域名或端口。"
        case "invalid_status", "no_body_status": "响应状态与正文不匹配。无正文状态请先清空正文。"
        case "managed_headers": "协议请求头由抓包组件管理，请保留原值。"
        case "invalid_headers": "请求头格式或大小不符合要求，请检查名称、值和重复行。"
        case "invalid_rule": "规则地址无效，请填写完整的 HTTP 或 HTTPS 接口地址。"
        case "unavailable", "credentials": unavailable
        case "invalid_command", "invalid_patch", "invalid_body": "修改未生效，请检查内容格式与编辑上限后重试。"
        default: disconnected
        }
    }
}
