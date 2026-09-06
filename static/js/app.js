(function () {
  var palette = [
    '#2d80bf', '#e07b39', '#3a9d6e', '#b04a5a', '#7a5fb5',
    '#c9a227', '#4a90a4', '#946b4a', '#5a7d2a', '#a45fa4',
  ];

  // ---- 侧边栏：对比勾选 / 批量删除 / 单条删除 ----
  var compareBtn = document.getElementById('compare-btn');
  var deleteSelectedBtn = document.getElementById('delete-selected-btn');
  var runChecks = Array.prototype.slice.call(document.querySelectorAll('.run-check'));

  function pickedRunIds() {
    return runChecks
      .filter(function (c) { return c.checked; })
      .map(function (c) { return c.value; });
  }

  function refreshSidebarActions() {
    var picked = pickedRunIds();
    if (compareBtn) {
      compareBtn.disabled = picked.length < 2;
      compareBtn.textContent = picked.length >= 2 ? '对比选中 ' + picked.length + ' 项' : '对比选中（需≥2项）';
    }
    if (deleteSelectedBtn) {
      deleteSelectedBtn.disabled = picked.length === 0;
      deleteSelectedBtn.textContent = picked.length > 0 ? '删除选中 ' + picked.length + ' 项' : '删除选中';
    }
  }

  runChecks.forEach(function (c) { c.addEventListener('change', refreshSidebarActions); });
  refreshSidebarActions();

  if (compareBtn) {
    compareBtn.addEventListener('click', function () {
      var picked = pickedRunIds();
      if (picked.length < 2) { return; }
      window.location.href = '/compare?runs=' + encodeURIComponent(picked.join(','));
    });
  }

  function requestDelete(url, body) {
    var options = { method: 'POST', headers: { 'X-Requested-With': 'fetch' } };
    if (body !== undefined) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }
    return fetch(url, options).then(function (resp) {
      return resp.json().catch(function () { return { ok: resp.ok }; });
    });
  }

  if (deleteSelectedBtn) {
    deleteSelectedBtn.addEventListener('click', function () {
      var picked = pickedRunIds();
      if (picked.length === 0) { return; }
      var lines = picked.map(function (rid) {
        var box = document.querySelector('.run-check[value="' + rid + '"]');
        var item = box ? box.closest('.run-item') : null;
        var title = item ? item.querySelector('.run-title') : null;
        return title ? '· ' + title.textContent.trim() : '· ' + rid;
      });
      var msg = '确定删除选中的 ' + picked.length + ' 条分析记录吗？\n\n' + lines.join('\n') + '\n\n对应文件将一并删除，删除后无法恢复。';
      if (!window.confirm(msg)) { return; }

      deleteSelectedBtn.disabled = true;
      requestDelete('/delete-batch', { runs: picked })
        .then(function (data) {
          var deletedCount = (data && data.deleted && data.deleted.length) || 0;
          var failed = (data && data.failed) || [];
          if (failed.length) {
            window.alert('已删除 ' + deletedCount + ' 条；' + failed.length + ' 条删除失败（文件可能被占用）。\n'
              + failed.map(function (f) { return '· ' + f.run_id + '：' + (f.error || '未知错误'); }).join('\n'));
          }
          window.location.href = '/';
        })
        .catch(function () {
          window.alert('删除请求失败，请重试。');
          deleteSelectedBtn.disabled = false;
        });
    });
  }

  document.querySelectorAll('.delete-btn[data-run-id]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var runId = btn.getAttribute('data-run-id');
      var fund = btn.getAttribute('data-fund-name') || runId;
      if (!window.confirm('确定删除「' + fund + '」（' + runId + '）的分析记录吗？\n\n对应文件将一并删除，删除后无法恢复。')) {
        return;
      }
      requestDelete('/delete/' + encodeURIComponent(runId))
        .then(function (data) {
          if (data && data.ok) {
            var item = btn.closest('.run-item');
            if (item) { item.remove(); }
            runChecks = runChecks.filter(function (c) { return c.isConnected; });
            if (window.location.pathname === '/view/' + runId) {
              window.location.href = '/';
            }
            refreshSidebarActions();
          } else {
            window.alert('删除失败：' + ((data && data.error) || '文件可能被占用，请关闭相关程序后重试。'));
          }
        })
        .catch(function () { window.alert('删除请求失败，请重试。'); });
    });
  });

  // ---- tab 切换 ----
  var tabs = document.querySelectorAll('.tab');
  var sections = document.querySelectorAll('.tab-content');
  tabs.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var target = btn.getAttribute('data-tab');
      tabs.forEach(function (b) { b.classList.remove('active'); });
      sections.forEach(function (s) { s.classList.remove('active'); });
      btn.classList.add('active');
      var targetNode = document.getElementById(target);
      if (targetNode) {
        targetNode.classList.add('active');
      }
    });
  });

  // ---- 侧边栏锚点：展开折叠块后跳转 ----
  document.querySelectorAll('.anchor-list a').forEach(function (link) {
    link.addEventListener('click', function () {
      var hash = link.getAttribute('href') || '';
      var target = document.getElementById(hash.slice(1));
      if (!target) { return; }
      if (target.tagName === 'DETAILS') { target.open = true; }
      var host = target.closest('details');
      if (host) { host.open = true; }
      var tabHost = target.closest('.tab-content');
      if (tabHost && !tabHost.classList.contains('active')) {
        var tabId = tabHost.id;
        var tabBtn = document.querySelector('.tab[data-tab="' + tabId + '"]');
        if (tabBtn) { tabBtn.click(); }
      }
    });
  });

  // ---- 图表绘制 ----
  var chartCards = window.CHART_CARDS || [];

  function hexAlpha(hex, alpha) {
    var r = parseInt(hex.slice(1, 3), 16);
    var g = parseInt(hex.slice(3, 5), 16);
    var b = parseInt(hex.slice(5, 7), 16);
    return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
  }

  function drawChart(canvasId, conf) {
    var el = document.getElementById(canvasId);
    if (!el || !conf) {
      return;
    }

    var chartType = conf.type === 'hbar' ? 'bar' : conf.type;
    var datasets;

    if (conf.type === 'scatter' || conf.type === 'bubble') {
      var scatterSeries = (Array.isArray(conf.datasets) && conf.datasets.length)
        ? conf.datasets
        : [{ label: conf.label || '', points: conf.points || [] }];
      datasets = scatterSeries.map(function (ds, i) {
        var color = palette[i % palette.length];
        return {
          label: ds.label || '',
          data: Array.isArray(ds.points) ? ds.points : [],
          borderColor: color,
          backgroundColor: hexAlpha(color, 0.85),
          pointRadius: 6,
        };
      });
    } else if (Array.isArray(conf.datasets) && conf.datasets.length) {
      datasets = conf.datasets.map(function (ds, i) {
        var color = palette[i % palette.length];
        return {
          label: ds.label || '',
          data: ds.values || [],
          borderColor: color,
          backgroundColor: conf.type === 'line' ? color : hexAlpha(color, 0.78),
          borderWidth: 2,
          tension: 0.25,
          fill: conf.type === 'line' ? false : true,
        };
      });
    } else {
      if (!Array.isArray(conf.labels) || !Array.isArray(conf.values)) {
        return;
      }
      var main = palette[0];
      datasets = [{
        label: conf.label || '',
        data: conf.values,
        borderColor: main,
        backgroundColor: palette,
        fill: conf.type === 'line' ? false : true,
        borderWidth: 2,
        tension: 0.25,
      }];
    }

    new Chart(el, {
      type: chartType,
      data: {
        labels: conf.labels || [],
        datasets: datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: conf.type === 'hbar' ? 'y' : undefined,
        plugins: {
          legend: {
            display: true,
            labels: { color: '#183a53', boxWidth: 12 },
          },
          tooltip: {
            callbacks: conf.type === 'hbar' || conf.type === 'bar' ? {
              title: function (items) {
                var item = items && items[0];
                if (!item) { return ''; }
                if (conf.names && conf.names[item.dataIndex] !== undefined) {
                  return conf.names[item.dataIndex];
                }
                return item.label;
              },
              label: function (ctx) {
                var v = ctx.parsed.y !== undefined && conf.type !== 'hbar' ? ctx.parsed.y : ctx.parsed.x;
                if (v === null || v === undefined) { return ctx.dataset.label + ': missing'; }
                return ctx.dataset.label + ': ' + Number(v).toLocaleString();
              },
            } : {},
          },
        },
        scales: conf.type === 'pie' || conf.type === 'doughnut' || conf.type === 'radar'
          ? {}
          : {
              x: { ticks: { color: '#335c78' }, grid: { color: '#e7f2fb' } },
              y: { ticks: { color: '#335c78' }, grid: { color: '#e7f2fb' } },
            },
      },
    });
  }

  chartCards.forEach(function (card) {
    drawChart(card.id, card);
  });
})();
