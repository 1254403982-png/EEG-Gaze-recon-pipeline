window.questionBank = window.questionBank || {};
window.questionBank.hard = window.questionBank.hard || [];
window.questionBank.hard.push(
  { id:47, title:"TCP拥塞控制与流量调节", domain:"计算机", difficulty:"高", diffClass:"is-high",
    summary:"TCP通过拥塞窗口和接收窗口协同调节发送速率，慢启动、拥塞避免、快速重传与恢复构成完整拥塞控制策略。",
    quickQs:["拥塞控制四个阶段","TCP Reno与CUBIC的区别","给我出道练习题","用通俗语言解释"],
    content:`<p>互联网上数十亿设备同时通信，却没有中央调度。当某条链路被数据"堵爆"时，路由器队列溢出、丢包。TCP协议靠一套精巧的<strong>拥塞控制</strong>机制，让每台设备自觉地"该快则快、该慢则慢"，维持全网稳定。</p>
<h3>两个窗口的协作</h3>
<p>发送方能发多少数据，由<strong>两个窗口取最小值</strong>决定：</p>
<div class="formula-block"><span class="formula-label">发送窗口</span>发送窗口 = min( cwnd, rwnd )<br>cwnd = 拥塞窗口（网络承载能力，发送方自调）<br>rwnd = 接收窗口（接收方缓冲区剩余，防撑爆接收方）</div>
<h3>拥塞控制的四个阶段</h3>
<table class="data-table">
<tr><th>阶段</th><th>窗口变化</th><th>触发条件</th></tr>
<tr><td>慢启动</td><td>指数增长(每RTT翻倍)</td><td>连接刚建立，cwnd从1 MSS起</td></tr>
<tr><td>拥塞避免</td><td>线性增长(每RTT+1)</td><td>cwnd达到阈值ssthresh</td></tr>
<tr><td>快速重传</td><td>立即重传</td><td>收到3个重复ACK（不等超时）</td></tr>
<tr><td>快速恢复</td><td>cwnd减半，进拥塞避免</td><td>快速重传后(Reno算法)</td></tr>
</table>
<h3>算法演进与公平性</h3>
<p>经典Reno之后，CUBIC（三次函数增长，适合长肥管道）成为Linux默认；BBR（基于模型测带宽）用于高延迟网络。<strong>公平性</strong>方面，TCP的"加性增、乘性减(AIMD)"机制让多条流共享瓶颈时自然收敛到均分带宽——就像多个司机自觉轮流通过窄桥。</p>
<h3>丢包就是信号：ssthresh 的动态调整</h3>
<p>慢启动和拥塞避免之间靠阈值<strong>ssthresh</strong>衔接。Reno检测到超时时，把ssthresh设为丢包前cwnd的一半，并把cwnd降到初始窗口后重新慢启动；收到3个重复ACK时则快速重传，进入快速恢复，恢复结束后把cwnd收缩到新的ssthresh并进入拥塞避免。重复ACK意味着仍有后续分组到达，通常比超时提供了更温和的拥塞证据。</p>
<h3>实际发送上限与带宽时延积</h3>
<p>有效在途数据上限是min(cwnd,rwnd)。即使网络cwnd很大，接收端通告的rwnd较小也会由流量控制限速。要充分利用带宽为B、往返时延为RTT的路径，窗口至少应接近带宽时延积B×RTT；高带宽高时延链路若窗口太小，每轮确认前就会空等。丢包也不总等于拥塞，无线随机误码会让基于丢包的Reno误判并不必要地降速，这是BBR等模型算法关注的动机之一。</p>`,
    quiz:[{ question:"综合全文，TCP为什么需要同时维护cwnd、rwnd并根据ACK或超时调整发送行为？", options:["A. rwnd保护接收缓冲区，cwnd估计网络承载能力，ACK或超时信号决定回退强度","B. 两个窗口都只用于加密数据，丢包不参与速率控制","C. cwnd由接收方固定，rwnd由路由器固定，发送方不能调整","D. 收到任何ACK都说明网络拥塞，发送方必须立即停止"], answerIndex:0 },
           { question:"材料如何解释“窗口已经很大，吞吐仍可能不高”和“发生丢包却未必真的拥塞”？", options:["A. 窗口大小与吞吐无关，丢包只能由接收端关闭连接造成","B. 有效窗口还受rwnd和带宽时延积限制，无线误码也可能被算法误判为拥塞","C. RTT越大，所需在途数据越少，因此大窗口必然提升吞吐","D. 只要cwnd已经很大，所有链路的吞吐都会接近物理带宽"], answerIndex:1 }] }
);
