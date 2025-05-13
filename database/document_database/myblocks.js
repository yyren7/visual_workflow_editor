import * as Blockly from 'blockly/core';
import * as python from 'blockly/python';
import 'blockly/blocks';

const INIT_TIMEOUT_MILLIS = -1;

class BlockUtility {
  constructor() {
    this.blockCount = {}; 
    this.deletedBlockCount = {};
    this.all_block_flow = []; 
    this.teachingJson = [];
    this.flagNames = [];
    this.flagParams = [];
    this.numberNames = [];
    this.externalInputNames = [];
    this.externalOutputNames = [];
    this.robotInputNames = [];
    this.robotOutputNames = [];
    this.robotName = "None";
    this.prevRobotName = "None";
  }

  findMissingNumber(ary) {
    // `ary` がオブジェクトのときにキーの数を取得
    const keys = Object.keys(ary);
    // オブジェクトが空の場合は1を返す
    if (keys.length === 0) {
      return 1;
    }
    // 現在の数値の最大値を取得
    const maxNumber = Math.max(...Object.values(ary));
    // 1から最大値までの数字がすべて存在するかをチェック
    const numberSet = new Set(Object.values(ary));
    for (let i = 1; i <= maxNumber; i++) {
      if (!numberSet.has(i)) {
        return i; // 穴抜けの数値を見つけたら返す
      }
    }
    // 穴抜けがない場合は、最大値に1を加算して返す
    return maxNumber + 1;
  }

  // ブロックの数を返すメソッド
  getBlockCount(type) {
    if (!this.blockCount[type]) {
      this.blockCount[type] = {};
    }
    return this.findMissingNumber(this.blockCount[type]) || 1;
  }

  addBlockCounter(type, blockId) {
    this.blockCount[type][blockId] = this.findMissingNumber(this.blockCount[type]);
  }

  deleteBlockCounter(type, blockId) {
    delete this.blockCount[type][blockId];
  }

  getBlockPositionOriginal(originalId, all_block_flow){
    for (let i = 0; i < all_block_flow.length; i++) {
      for (let j = 0; j < all_block_flow[i].length; j++) {
        if(all_block_flow[i][j].originalId === originalId){
          return {
            thread_no: i, 
            flow_no: j, 
        };
        }
      }
    }
    return {
      thread_no: -1, 
      flow_no: -1, 
    };
  }

  getBlockPositionCustom(custom_id, all_block_flow){
    for (let i = 0; i < all_block_flow.length; i++) {
      for (let j = 0; j < all_block_flow[i].length; j++) {
        if(all_block_flow[i][j].custom_id === custom_id){
          return {
            thread_no: i, 
            flow_no: j, 
        };
        }
      }
    }
    return {
      thread_no: -1, 
      flow_no: -1, 
    };
  }
}

class BlockFlow {
  // クラス変数定義
  constructor(blockUtilsIns) {
    this.blockUtilsIns = blockUtilsIns;
    this.workspace = Blockly.getMainWorkspace();

    // ブロックが追加される度に行う動作を定義
    this.addBlockListener();
    this.deleteBlockListener();

  }

  // ブロック追加のイベントリスナーを設定するメソッド
  addBlockListener() {
    const self = this; // thisの値を安定化させる
    self.workspace.addChangeListener(function (event) {
      if (event.type === Blockly.Events.BLOCK_CREATE) {
        const blockId = event.blockId;
        const block = self.workspace.getBlockById(blockId);
        self.blockUtilsIns.addBlockCounter(block.type, blockId); // ブロックの数を更新
      }
    });
  }

  deleteBlockListener() {
    const self = this; // thisの値を安定化させる  
    self.workspace.addChangeListener(function (event) {
      if (event.type === Blockly.Events.BLOCK_DELETE) { // ブロックが削除された場合のみ処理を行う
        const oldXml = event.oldXml;
        if (oldXml && oldXml.tagName === 'block') {
          const type = oldXml.getAttribute('type');
          const blockId = oldXml.id;
          self.blockUtilsIns.deleteBlockCounter(type, blockId);
        }
      }
    });
  }

  checkBlockId(process_flow, block_id) {
    let key = block_id;
    let key_index = -1;
    for (let j = 0; j < process_flow.length; j++) {
      if (key === process_flow[j].originalId){
        key_index = j;
      }
    }  
    return key_index;
  }

  convNum2Device(seq_number, offset){
    return seq_number + offset;
    // const word_no = Math.floor(seq_number / 100) + Math.floor(offset / 16)
    // const bit_no  = (seq_number % 100) + (offset % 16)
    // const relay_no = word_no * 100 + bit_no
    // return relay_no;
  }

  getPreviousBlockId(blocks, blockId) {
    for (let i = 0; i < blocks.length; i++) {
        let block = blocks[i];
        if (block.getAttribute("id") === blockId) {
            let parentBlock = block.parentNode;
            while (parentBlock) {
              const parentBlockId = parentBlock.getAttribute("id");
              const parentHasDisabled = parentBlock.getAttribute("disabled");
              if(parentBlockId){
                const blockInstance = this.workspace.getBlockById(parentBlockId);
                const hasBlockFlow = blockInstance.hasBlockFlow;
                // 親ブロックが存在しているなら
                if ((parentBlock.tagName === "block") && (hasBlockFlow) && !(parentHasDisabled)){
                    return parentBlockId;
                }
              }
              parentBlock = parentBlock.parentNode; // 親をたどる
            }
            break;
        }
    }
    return null; // 前に接続されたブロックが見つからない場合
  }

  convertXMLtoArray(xml) {
    let blocks = xml.getElementsByTagName("block");
    let all_block_flow = [];
    let block_flow = [];
    let block_cnt = 0;
    // seq_stepの配列番号
    let init_start_addr = 0;
    let init_stop1_addr = 1000;
    let init_stop2_addr = 2000;
    let init_stop3_addr = 3000;
    let init_stop4_addr = 4000;
    let init_stop5_addr = 5000;
    let init_stop6_addr = 6000;
    let init_stop7_addr = 7000;
    let init_stop8_addr = 8000;
    let init_stop9_addr = 9000;
    let init_stop10_addr = 10000;
    let event_survival_addr = -1;

    // パーサーを使用してXMLをパース
    const parser = new DOMParser();
    const xmlString = Blockly.Xml.domToPrettyText(xml);
    const xmlDoc = parser.parseFromString(xmlString, "application/xml");

    // ブロックの走査
    for (let i = 0; i < blocks.length; i++) {
      const block_contents = [];
      const block = blocks[i];
      // const survival1_contents = [];
      const survival_contents = [];
      const survival_id_contents = [];
      const onset_contents = [];
      const onset_id_contents = [];
      const block_type = block.getAttribute("type");
      const block_id = block.getAttribute("id");
      const hasDisabled = block.getAttribute("disabled");
      const blockInstance = this.workspace.getBlockById(block_id);
      const hasBlockNo = blockInstance.hasBlockNo;
      const hasBlockFlow = blockInstance.hasBlockFlow;
      const custom_block_id = blockInstance.customId;
      const blockColor = blockInstance.originalColor;

      // シーケンスアドレスが必要なブロック　かつ　ブロックが無効化でなければ
      if((hasBlockFlow) && !(hasDisabled)){
        // console.log('--------------------------------------------');
        ///////////////////////////////////
        // 当該情報
        ///////////////////////////////////
        block_contents.custom_id = custom_block_id;
        block_contents.hasBlockNo = hasBlockNo;
        block_contents.index = block_cnt;
        block_contents.originalType = block_type;
        block_contents.originalId = block_id;
        block_contents.originalColor = blockColor;

        ///////////////////////////////////
        // 自作関数情報
        ///////////////////////////////////
        // 関数実行ブロック
        if (block_type === 'procedures_callnoreturn') {
          // console.log(`me:${block_type}`);
          
          // CSSセレクターで直接取得
          const fields = xmlDoc.querySelectorAll('field[name="NAME"]');  // 全てのfield[name="NAME"]を取得
          const funcName = block.querySelector('mutation').getAttribute('name');  // function nameを取得
        
          // 各fieldをループして処理する
          fields.forEach((field) => {
            if (field.textContent.trim() === funcName) {  // funcNameと一致するfieldを確認
              const defBlock = field.closest('block');  // 対応するblockを取得
              if (defBlock) {
                onset_id_contents.push(defBlock.getAttribute("id"));                
              }
            }
          });
          block_contents.onset_id = onset_id_contents;
        }
        
        // 関数定義ブロック
        if (block_type === 'procedures_defnoreturn') {
          // console.log(`me:${block_type}`);
        
          // mutation[name="do something"]があるすべてのブロックを取得
          const fieldNameElement = block.querySelector('field[name="NAME"]');
          const funcName = fieldNameElement.textContent.trim();
          const mutations = xmlDoc.querySelectorAll(`mutation[name="${funcName}"]`);
          
          // 最初に一致するblockを取得し、その情報を表示
          mutations.forEach(mutation => {
            const callBlock = mutation.closest('block');
            if (callBlock) {
              survival_id_contents.push(callBlock.getAttribute("id"));  
            }
          });
          block_contents.survival_id = survival_id_contents;
        }

        ///////////////////////////////////
        // 接続元情報
        ///////////////////////////////////
        // 変数定義
        let parent_tag = block.parentNode.tagName;
        let key_index = 0;
        let key = '';

        switch (parent_tag) {
          // 最初のブロックなら 
          case 'xml':
            if(i > 0){
              all_block_flow.push(block_flow);
              block_flow = [];
            }
            // サブプロセス開始ブロックなら
            if((block_type == 'select_robot') ||
              //  (block_type == 'procedures_defnoreturn') ||
               (block_type == 'start_thread') ||
               (block_type == 'create_event')){
              survival_contents.push(992002);
              block_contents.survival1 = survival_contents;
              block_contents.prevIndex = -1;
              block_contents.prevBranchNum = 1;
            }
            break;
          // 接続元ブロックが内包ブロックなら
          case 'statement':
            // elseifとelseの数をカウント
            let children = block.parentNode.parentNode.childNodes;
            let index = 0;
            let elseif_cnt = 0;
            let else_cnt = 0;
            for(let element of children) {
              let child_tag = children[index].nodeName;
              if(child_tag === 'mutation'){
                if(children[index].getAttribute('elseif') != null){
                  elseif_cnt = Number(children[index].getAttribute('elseif'));
                }
                if(children[index].getAttribute('else') != null){
                  else_cnt = Number(children[index].getAttribute('else'));
                }
                break;
              }
              index++;
            }
            let branch_cnt = elseif_cnt+else_cnt; // ELSEのstop番号判定用

            // 接続元ブロックの要素番号算出
            key_index = 0;
            key = block.parentNode.parentNode.getAttribute('id');
            key_index = this.checkBlockId(block_flow, key);

            // 内包ブロックのどの領域が接続元か確認
            switch(block.parentNode.getAttribute('name')){
              // 自作関数定義ブロック
              case 'STACK':
                block_contents.prevBranchNum = 1;
                survival_contents.push(block_flow[key_index].stop1);
                block_contents.survival1 = survival_contents;
              break;
              // create_eventブロック
              case 'EVENT':
                block_contents.prevBranchNum = 1;
                event_survival_addr = block_flow[key_index].stop1;
                survival_contents.push(event_survival_addr);
                block_contents.survival1 = survival_contents;
                break;
              // これ以降IFブロック
              case 'DO':
                block_contents.prevBranchNum = 1;
                survival_contents.push(block_flow[key_index].stop1);
                block_contents.survival1 = survival_contents;
                break;
              case 'DO0':
                block_contents.prevBranchNum = 1;
                survival_contents.push(block_flow[key_index].stop1);
                block_contents.survival1 = survival_contents;
                break;
              case 'DO1':
                block_contents.prevBranchNum = 2;
                survival_contents.push(block_flow[key_index].stop2);
                block_contents.survival1 = survival_contents;
                break;
              case 'DO2':
                block_contents.prevBranchNum = 3;
                survival_contents.push(block_flow[key_index].stop3);
                block_contents.survival1 = survival_contents;
                break;
              case 'DO3':
                block_contents.prevBranchNum = 4;
                survival_contents.push(block_flow[key_index].stop4);
                block_contents.survival1 = survival_contents;
                break;
              case 'DO4':
                block_contents.prevBranchNum = 5;
                survival_contents.push(block_flow[key_index].stop5);
                block_contents.survival1 = survival_contents;
                break;
              case 'DO5':
                block_contents.prevBranchNum = 6;
                survival_contents.push(block_flow[key_index].stop6);
                block_contents.survival1 = survival_contents;
                break;
              case 'DO6':
                block_contents.prevBranchNum = 7;
                survival_contents.push(block_flow[key_index].stop7);
                block_contents.survival1 = survival_contents;
                break;
              case 'DO7':
                block_contents.prevBranchNum = 8;
                survival_contents.push(block_flow[key_index].stop8);
                block_contents.survival1 = survival_contents;
                break;
              case 'DO8':
                block_contents.prevBranchNum = 9;
                survival_contents.push(block_flow[key_index].stop9);
                block_contents.survival1 = survival_contents;
                break;
              case 'DO9':
                block_contents.prevBranchNum = 10;
                survival_contents.push(block_flow[key_index].stop10);
                block_contents.survival1 = survival_contents;
                break;
              case 'ELSE':
                block_contents.prevBranchNum = branch_cnt + 1;
                if (branch_cnt === 1) 
                {
                  survival_contents.push(block_flow[key_index].stop2);
                  block_contents.survival1 = survival_contents;
                }
                else if (branch_cnt === 2) {
                  survival_contents.push(block_flow[key_index].stop3);
                  block_contents.survival1 = survival_contents;
                }
                else if (branch_cnt === 3) {
                  survival_contents.push(block_flow[key_index].stop4);
                  block_contents.survival1 = survival_contents;
                }
                else if (branch_cnt === 4) {
                  survival_contents.push(block_flow[key_index].stop5);
                  block_contents.survival1 = survival_contents;
                }
                else if (branch_cnt === 5) {
                  survival_contents.push(block_flow[key_index].stop6);
                  block_contents.survival1 = survival_contents;
                }
                else if (branch_cnt === 6) {
                  survival_contents.push(block_flow[key_index].stop7);
                  block_contents.survival1 = survival_contents;
                }
                else if (branch_cnt === 7) {
                  survival_contents.push(block_flow[key_index].stop8);
                  block_contents.survival1 = survival_contents;
                }
                else if (branch_cnt === 8) {
                  survival_contents.push(block_flow[key_index].stop9);
                  block_contents.survival1 = survival_contents;
                }
                else if (branch_cnt === 9) {
                  survival_contents.push(block_flow[key_index].stop10);
                  block_contents.survival1 = survival_contents;
                }
                break;
            }
            block_contents.prevIndex = block_flow[key_index].index;
            break;

          // 接続元が通常のブロックなら
          case 'next':
            // 自身がuponブロックなら
            if (block_contents.originalType.includes('upon')){
              survival_contents.push(event_survival_addr);
              block_contents.survival1 = survival_contents; 
              block_contents.prevIndex = -1;
                // break;
            }
            // uponブロック以外なら
            else{
              // 接続元ブロックがifじゃないこと確認
              let previousBlockId = this.getPreviousBlockId(blocks, block.id);
              let previousBlockType = this.workspace.getBlockById(previousBlockId).type;
              // 1つ前のブロックが if ならwhileを継続
              while (previousBlockType.includes('controls_if')){
                // console.log('post', previousBlockType);
                previousBlockId = this.getPreviousBlockId(blocks, previousBlockId);
                previousBlockType = this.workspace.getBlockById(previousBlockId).type;
              }
              // 接続元ブロックの要素番号算出
              key_index = 0;
              key = previousBlockId;
              key_index = this.checkBlockId(block_flow, key);  
              block_contents.prevBranchNum = 1;
              survival_contents.push(block_flow[key_index].stop1);
              block_contents.prevIndex = block_flow[key_index].index;
                // サブプロセス開始ブロックなら
              if((block_type != 'start_thread') ||
                (block_type != 'create_event')){
                block_contents.survival1 = survival_contents; 
              }
              break;

            }
          default:
          }

        ///////////////////////////////////
        // 当該情報
        ///////////////////////////////////
        block_contents.start = this.convNum2Device(init_start_addr, block_cnt);
        block_contents.stop1 = this.convNum2Device(init_stop1_addr,  block_cnt);

        ///////////////////////////////////
        // 接続先情報
        ///////////////////////////////////
        let children = block.childNodes;
        let index = 0;
        let elseif_cnt = 0;
        let else_cnt = 0;
      
        for(let element of children) {
          let child_tag = children[index].nodeName;
          if(child_tag === 'mutation'){
            if(children[index].getAttribute('elseif') != null){
              elseif_cnt = Number(children[index].getAttribute('elseif'));
            }
            if(children[index].getAttribute('else') != null){
              else_cnt = Number(children[index].getAttribute('else'));
            }
            break;
          }
          index++;
        }
        
        // 条件分岐用アドレス設定
        let branch_cnt = elseif_cnt+else_cnt;
        switch(branch_cnt){
          case 1:
            block_contents.stop1 = this.convNum2Device(init_stop1_addr, block_cnt);
            block_contents.stop2 = this.convNum2Device(init_stop2_addr, block_cnt);
            break;
          case 2:
            block_contents.stop1 = this.convNum2Device(init_stop1_addr, block_cnt);
            block_contents.stop2 = this.convNum2Device(init_stop2_addr, block_cnt);
            block_contents.stop3 = this.convNum2Device(init_stop3_addr, block_cnt);
            break;
          case 3:
            block_contents.stop1 = this.convNum2Device(init_stop1_addr, block_cnt);
            block_contents.stop2 = this.convNum2Device(init_stop2_addr, block_cnt);
            block_contents.stop3 = this.convNum2Device(init_stop3_addr, block_cnt);
            block_contents.stop4 = this.convNum2Device(init_stop4_addr, block_cnt);
            break;
          case 4:
            block_contents.stop1 = this.convNum2Device(init_stop1_addr, block_cnt);
            block_contents.stop2 = this.convNum2Device(init_stop2_addr, block_cnt);
            block_contents.stop3 = this.convNum2Device(init_stop3_addr, block_cnt);
            block_contents.stop4 = this.convNum2Device(init_stop4_addr, block_cnt);
            block_contents.stop5 = this.convNum2Device(init_stop5_addr, block_cnt);
            break;
          case 5:
            block_contents.stop1 = this.convNum2Device(init_stop1_addr, block_cnt);
            block_contents.stop2 = this.convNum2Device(init_stop2_addr, block_cnt);
            block_contents.stop3 = this.convNum2Device(init_stop3_addr, block_cnt);
            block_contents.stop4 = this.convNum2Device(init_stop4_addr, block_cnt);
            block_contents.stop5 = this.convNum2Device(init_stop5_addr, block_cnt);
            block_contents.stop6 = this.convNum2Device(init_stop6_addr, block_cnt);
            break;
          case 6:
            block_contents.stop1 = this.convNum2Device(init_stop1_addr, block_cnt);
            block_contents.stop2 = this.convNum2Device(init_stop2_addr, block_cnt);
            block_contents.stop3 = this.convNum2Device(init_stop3_addr, block_cnt);
            block_contents.stop4 = this.convNum2Device(init_stop4_addr, block_cnt);
            block_contents.stop5 = this.convNum2Device(init_stop5_addr, block_cnt);
            block_contents.stop6 = this.convNum2Device(init_stop6_addr, block_cnt);
            block_contents.stop7 = this.convNum2Device(init_stop7_addr, block_cnt);
            break;
          case 7:
            block_contents.stop1 = this.convNum2Device(init_stop1_addr, block_cnt);
            block_contents.stop2 = this.convNum2Device(init_stop2_addr, block_cnt);
            block_contents.stop3 = this.convNum2Device(init_stop3_addr, block_cnt);
            block_contents.stop4 = this.convNum2Device(init_stop4_addr, block_cnt);
            block_contents.stop5 = this.convNum2Device(init_stop5_addr, block_cnt);
            block_contents.stop6 = this.convNum2Device(init_stop6_addr, block_cnt);
            block_contents.stop7 = this.convNum2Device(init_stop7_addr, block_cnt);
            block_contents.stop8 = this.convNum2Device(init_stop8_addr, block_cnt);
            break;
          case 8:
            block_contents.stop1 = this.convNum2Device(init_stop1_addr, block_cnt);
            block_contents.stop2 = this.convNum2Device(init_stop2_addr, block_cnt);
            block_contents.stop3 = this.convNum2Device(init_stop3_addr, block_cnt);
            block_contents.stop4 = this.convNum2Device(init_stop4_addr, block_cnt);
            block_contents.stop5 = this.convNum2Device(init_stop5_addr, block_cnt);
            block_contents.stop6 = this.convNum2Device(init_stop6_addr, block_cnt);
            block_contents.stop7 = this.convNum2Device(init_stop7_addr, block_cnt);
            block_contents.stop8 = this.convNum2Device(init_stop8_addr, block_cnt);
            block_contents.stop9 = this.convNum2Device(init_stop9_addr, block_cnt);
            break;
          case 9:
            block_contents.stop1 = this.convNum2Device(init_stop1_addr, block_cnt);
            block_contents.stop2 = this.convNum2Device(init_stop2_addr, block_cnt);
            block_contents.stop3 = this.convNum2Device(init_stop3_addr, block_cnt);
            block_contents.stop4 = this.convNum2Device(init_stop4_addr, block_cnt);
            block_contents.stop5 = this.convNum2Device(init_stop5_addr, block_cnt);
            block_contents.stop6 = this.convNum2Device(init_stop6_addr, block_cnt);
            block_contents.stop7 = this.convNum2Device(init_stop7_addr, block_cnt);
            block_contents.stop8 = this.convNum2Device(init_stop8_addr, block_cnt);
            block_contents.stop9 = this.convNum2Device(init_stop9_addr, block_cnt);
            block_contents.stop10 = this.convNum2Device(init_stop10_addr, block_cnt);
            break;
        }
        // ブロック情報をブロック配列に格納
        block_flow.push(block_contents);

        // ブロックカウントインクリメント
        block_cnt = block_cnt + 1;

      }
      // 全体のブロックフローに追加
      if(i === blocks.length-1){
        all_block_flow.push(block_flow);
        block_flow = [];
      }
      // block_cnt = block_cnt + 1;
    } 


    ///////////////////////////////////
    // 自作関数情報
    ///////////////////////////////////
    for (let i = 0; i < all_block_flow.length; i++) {
      for (let j = 0; j < all_block_flow[i].length; j++) {
        // 関数呼出ブロック
        if (all_block_flow[i][j].onset_id){
          let onset_contents = [];
          // 対象関数の最後に接続されたブロックアドレスを格納
          all_block_flow[i][j].onset_id.forEach((element, index) => {
            const indexPair = this.blockUtilsIns.getBlockPositionOriginal(all_block_flow[i][j].onset_id[index], all_block_flow);
            if (indexPair.thread_no >= 0){
              const lastBlockNo = all_block_flow[indexPair.thread_no].length;
              onset_contents.push(all_block_flow[indexPair.thread_no][lastBlockNo-1].stop1);
              all_block_flow[i][j].defFuncStart = all_block_flow[indexPair.thread_no][1-1].start;
            }
          });
        // 開始条件をまとめて格納
        all_block_flow[i][j].onset = onset_contents;
      }

        // 関数定義ブロック
        if (all_block_flow[i][j].survival_id){
          let survival_contents = [];
          // 対象関数の最後に接続されたブロックアドレスを格納
          all_block_flow[i][j].survival_id.forEach((element, index) => {
            const indexPair = this.blockUtilsIns.getBlockPositionOriginal(all_block_flow[i][j].survival_id[index], all_block_flow);
            if (indexPair.thread_no >= 0 && indexPair.flow_no >= 0){
              survival_contents.push(all_block_flow[indexPair.thread_no][indexPair.flow_no].start);
              all_block_flow[i][j].prevIndex = all_block_flow[indexPair.thread_no][indexPair.flow_no].index;
              all_block_flow[i][j].prevBranchNum = 1;
            }
          });
        // 開始条件をまとめて格納
        all_block_flow[i][j].survival1 = survival_contents;
      }
      }
    }

    ///////////////////////////////////
    // ループリセット情報
    ///////////////////////////////////
    for (let i = 0; i < all_block_flow.length; i++) {
      // loopの場所を確認
      let found_loop_index = -1;
      for (let j = 0; j < all_block_flow[i].length; j++) {
        let block_type = this.workspace.getBlockById(all_block_flow[i][j].originalId).type;
        if ((block_type === 'controls_whileUntil') || (block_type === 'loop')){
          found_loop_index = j;
          break;
        }
      }
      // returnの場所を確認し、loopにリセットアドレスを追加
      if (found_loop_index >= 0){
        let reset_contents = [];
        for (let j = 0; j < all_block_flow[i].length; j++) {
          let block_type = this.workspace.getBlockById(all_block_flow[i][j].originalId).type;
          if (block_type === 'return'){
            reset_contents.push(all_block_flow[i][j].stop1);
          }
        }
        all_block_flow[i][found_loop_index].reset = reset_contents;
      }
    }


    // デバッグ用ログ出力
    let all_block_flow_buf = all_block_flow;
    all_block_flow_buf.forEach(obj => {
      const filteredObj = {};
      for (const key in obj) {
        delete obj[key].type;
        delete obj[key].id;
        filteredObj[key] = obj[key];
      }
      // console.log(filteredObj);
    });

    return all_block_flow;
  }

  updateBlockFlow(){  
    //////////////////////////////////////////////////
    // ブロックのフロー作成
    //////////////////////////////////////////////////  
    let originalXml = Blockly.Xml.workspaceToDom(this.workspace);
    this.blockUtilsIns.all_block_flow = this.convertXMLtoArray(originalXml);
    // ブロックのxml取得
    let customXml = Blockly.Xml.workspaceToDom(this.workspace);  
    // ブロックNo.をxmlに追加
    customXml.querySelectorAll('block').forEach(blockXml => {
      const block = this.workspace.getBlockById(blockXml.getAttribute('id'));
      if (block && block.blockNo) {
        blockXml.setAttribute('data-blockNo', block.blockNo);
      }
    });
    // プログラム自動バックアップ
    let xmlPrettyText = Blockly.Xml.domToPrettyText(customXml);
    localStorage.setItem('program_backup', xmlPrettyText);
    // debug
    // console.log(this.blockUtilsIns.all_block_flow);
    // console.log(xmlPrettyText);
  }
}


class BlockForm {
  constructor(blockUtilsIns) {
    this.blockUtilsIns = blockUtilsIns;
    this.workspace = Blockly.getMainWorkspace();

  }

  setBlockTeaching(teachingJson) {
    // ポイント名リスト作成
    let pointName = [];
    for (let key in teachingJson) {
      pointName.push([teachingJson[key]['name'], key]);
    }

    this.blockUtilsIns.teachingJson = teachingJson;
    this.options = pointName;

    // const local_wk = Blockly.getMainWorkspace();
    this.workspace.getAllBlocks().forEach(block => {
      if (block.type === 'moveL') {
        const dropdownField = block.getField('point_name_list');
        if (dropdownField) {
          dropdownField.menuGenerator_ = pointName;
          const selectedValue = dropdownField.getValue();
          block.setTooltip(`X :${teachingJson[selectedValue]['x_pos']}\n
                            Y :${teachingJson[selectedValue]['y_pos']}\n
                            Z :${teachingJson[selectedValue]['z_pos']}\n
                            Rz:${teachingJson[selectedValue]['rz_pos']}\n
                            Ry:${teachingJson[selectedValue]['ry_pos']}\n
                            Rx:${teachingJson[selectedValue]['rx_pos']}\n`);
        }
      }
      if (block.type === 'moveP') {
        const dropdownField = block.getField('point_name_list');
        if (dropdownField) {
          dropdownField.menuGenerator_ = pointName;
          const selectedValue = dropdownField.getValue();
          block.setTooltip(`X :${teachingJson[selectedValue]['x_pos']}\n
                            Y :${teachingJson[selectedValue]['y_pos']}\n
                            Z :${teachingJson[selectedValue]['z_pos']}\n
                            Rz:${teachingJson[selectedValue]['rz_pos']}\n
                            Ry:${teachingJson[selectedValue]['ry_pos']}\n
                            Rx:${teachingJson[selectedValue]['rx_pos']}\n`);
        }
      }
      if (block.type === 'set_pallet') {
        const dropdownFieldA = block.getField('A_name_list');
        if (dropdownFieldA) dropdownFieldA.menuGenerator_ = pointName;
        const dropdownFieldB = block.getField('B_name_list');
        if (dropdownFieldB) dropdownFieldB.menuGenerator_ = pointName;
        const dropdownFieldC = block.getField('C_name_list');
        if (dropdownFieldC) dropdownFieldC.menuGenerator_ = pointName;
        const dropdownFieldD = block.getField('D_name_list');
        if (dropdownFieldD) dropdownFieldD.menuGenerator_ = pointName;
        
      }
    });
  }

  updateDropdownParam(block, fieldName, menuGenerator, parameterJson) {
    const dropdownField = block.getField(fieldName);
    if (dropdownField) {
      dropdownField.menuGenerator_ = menuGenerator;
      const selectedValue = dropdownField.getValue();
      block.setTooltip(`Value :${parameterJson[selectedValue]['value']}`);
      block.render();
    }
  }

  setBlockParameter(numberJson, flagJson) {
    // 数値パラメータリスト作成
    const numberNames = [];
    for (let key in numberJson) {
      numberNames.push([numberJson[key]['name'], key]);
    }
    this.numberNames = numberNames;

    // フラグパラメータリスト作成
    const flagNames = [];
    for (let key in flagJson) {
      flagNames.push([flagJson[key]['name'], key]);
    }
    this.flagNames = flagNames;

    // 見た目変更
    this.workspace.getAllBlocks().forEach(block => {
      // 数値
      if (block.type === 'wait_timer') {
        this.updateDropdownParam(block, 'name', numberNames, numberJson);
      }
      else if (block.type === 'set_number') {
        this.updateDropdownParam(block, 'name', numberNames, numberJson);
      }
      else if (block.type === 'set_number_upon') {
        this.updateDropdownParam(block, 'name', numberNames, numberJson);
      }
      else if (block.type === 'math_custom_number') {
        this.updateDropdownParam(block, 'name', numberNames, numberJson);
      }
      else if (block.type === 'set_output_during') {
        this.updateDropdownParam(block, 'name', numberNames, numberJson);
      }
      // フラグ
      else if (block.type === 'set_flag') {
        this.updateDropdownParam(block, 'name', flagNames, flagJson);
      }
      else if (block.type === 'set_flag_upon') {
        this.updateDropdownParam(block, 'name', flagNames, flagJson);
      }
      else if (block.type === 'logic_custom_flag') {
        this.updateDropdownParam(block, 'name', flagNames, flagJson);
      }
    });
  }

  setBlockOverride(override) {
    if (!override){
      this.blockUtilsIns.override = 0;
    }
    else{
      this.blockUtilsIns.override = override;
    }
  }

  setBlockRobotName(robotName) {
    // 差分があれば、動的に変更
    if (this.prevRobotName !== robotName){
      let allBlocks = this.workspace.getAllBlocks();
      allBlocks.forEach(function(block) {
        if (block.type === 'select_robot') { // ブロックタイプを確認
          block.setFieldValue(`${robotName}`, 'robotName');
        }
      });
    }

    // ブロック配置時の初期値更新
    this.robotName = robotName;
    // ロボット名更新
    this.prevRobotName = robotName;
  }        

  updateDropdownIO(block, fieldName, menuGenerator) {
    const dropdownField = block.getField(fieldName);
    if (dropdownField) {
      dropdownField.menuGenerator_ = menuGenerator;
      block.render();
    }
  }

  setBlockIOName(robotIONames, externalIONames) {
      // 表示名設定
      this.robotInputNames = robotIONames[0];
      this.robotOutputNames = robotIONames[1];
      this.externalInputNames = externalIONames[0];
      this.externalOutputNames = externalIONames[1];

      // 表示名更新
      const local_wk = Blockly.getMainWorkspace();
      local_wk.getAllBlocks().forEach(block => {
        // ロボット
        if (block.type === 'wait_input') {
          this.updateDropdownIO(block, 'input_pin_name', this.robotInputNames);
        } 
        else if (block.type === 'set_output') {
          this.updateDropdownIO(block, 'output_pin_name', this.robotOutputNames);
        } 
        else if (block.type === 'set_output_until') {
          this.updateDropdownIO(block, 'input_pin_name', this.robotInputNames);
          this.updateDropdownIO(block, 'output_pin_name', this.robotOutputNames);
        } 
        else if (block.type === 'set_output_during') {
          this.updateDropdownIO(block, 'output_pin_name', this.robotOutputNames);
        }
        else if (block.type === 'robot_io') {
          this.updateDropdownIO(block, 'input_pin_name', this.robotInputNames);
        }
        // 外付けIO
        else if (block.type === 'wait_external_io_input') {
          this.updateDropdownIO(block, 'input_pin_name', this.externalInputNames);
        } 
        else if (block.type === 'set_external_io_output') {
          this.updateDropdownIO(block, 'output_pin_name', this.externalOutputNames);
        } 
        else if (block.type === 'set_external_io_output_until') {
          this.updateDropdownIO(block, 'input_pin_name', this.externalInputNames);
          this.updateDropdownIO(block, 'output_pin_name', this.externalOutputNames);
        } 
        else if (block.type === 'set_external_io_output_during') {
          this.updateDropdownIO(block, 'output_pin_name', this.externalOutputNames);
        }
        else if (block.type === 'external_io') {
          this.updateDropdownIO(block, 'input_pin_name', this.externalInputNames);
        }
      });
  }   
  
  reviseBlockCount() {
    //////////////////////////////////////////////////
    // コピペ対応
    //////////////////////////////////////////////////  
    let blockPresenceID = [];
    this.workspace.getAllBlocks().forEach(block => {
      // ブロックNoが存在するブロックなら
      if (block.hasBlockNo) {
        // 削除対応で使う配列作成
        blockPresenceID.push(block.id);
        // 登録されていないブロックがあれば
        if (typeof this.blockUtilsIns.blockCount[block.type][block.id] === 'undefined'){
          // ブロック番号の表示を変更
          const newNo = this.blockUtilsIns.getBlockCount(block.type) 
          const field = block.getField('blockNoField');
          if (field) field.setValue(`(${newNo})`); // 番号表示ある場合のみ更新
          // 内部IDを変更
          block.blockNo = newNo;
          block.customId = block.type + '@' + newNo;
          // 共有カウンタ更新 
          this.blockUtilsIns.addBlockCounter(block.type, block.id)
        }
      }
    });
    //////////////////////////////////////////////////
    // 削除対応
    //////////////////////////////////////////////////  
    let dictionary = this.blockUtilsIns.blockCount;
    for (let key in dictionary) {
      // "key（関数名）"を持っていれば
      if (dictionary.hasOwnProperty(key)) {
        let subDictionary = dictionary[key];
          // サブオブジェクトがオブジェクトである場合のみ処理
          if (typeof subDictionary === 'object' && subDictionary !== null) {
              for (let subKey in subDictionary) {
                  if (subDictionary.hasOwnProperty(subKey) && !blockPresenceID.includes(subKey)) {
                      delete subDictionary[subKey];
                  }
              }
          }
      }
    }
  }   

    // 共通の処理を持つ関数
    addTimeoutOption(block) {
      // コンテキストメニューのカスタマイズ
      block.customContextMenu = function(options) {
      //   for (let i = 0; i < options.length; i++) {
      //     // "Disable Block"オプションを削除
      //     if (options[i].text === 'Disable Block') {
      //         options.splice(i, 1);
      //         break;
      //       }
      //   }
        // その他のオプションを追加
        let setTimeoutOption = {
          text: "Set Timeout",
          enabled: true,
          callback: () => {
            let newTimeout = prompt("Enter the timeout in milliseconds (Valid: 0 ~ 2147483648, Disable: -1)", block.timeoutMillis);
            if (newTimeout !== null && !isNaN(newTimeout)) {
              block.timeoutMillis = parseInt(newTimeout, 10);
            }
          }
        };
        options.push(setTimeoutOption);
      };

      // XML に保存する処理
      block.mutationToDom = function() {
        let container = Blockly.utils.xml.createElement('mutation');
        container.setAttribute('timeout', block.timeoutMillis);
        return container;
      };

      // XML から復元する処理
      block.domToMutation = function(xmlElement) {
        let timeout = xmlElement.getAttribute('timeout');
        if (timeout !== null) {
          block.timeoutMillis = parseInt(timeout, 10);
        }
      };
    }

  defineBlockForm() {
      let self = this;      
      // カスタムテキストフィールドの定義
      Blockly.FieldBlockId = class extends Blockly.Field {
        constructor(text, opt_validator) {
          super(text, opt_validator);
        }
      };

      Blockly.Blocks['display_procedures_defreturn'] = {
        init: function() {
            this.appendDummyInput()
                .appendField("to")
                .appendField(new Blockly.FieldTextInput("functionName"), "NAME");            
            this.appendStatementInput("DO")  // ステートメント入力を追加
                // .appendField("実行する処理"); // フィールド名を設定    
            this.setColour(290);
            this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
            self.addTimeoutOption(this);
       }
      };

      Blockly.Blocks['set_speed'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("set speed to")
              .appendField(new Blockly.FieldNumber(100), "speed")
              .appendField("%")
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(40);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };

      Blockly.Blocks['wait_ready'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField("wait ready button")
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(40);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };

      Blockly.Blocks['wait_run'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField("wait run button")
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(40);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };

      Blockly.Blocks['system_variable'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type; 
          this.hasBlockNo = false; 
          this.hasBlockFlow = false; 
          this.appendDummyInput()
              .appendField(new Blockly.FieldDropdown([
                                                      // ["systemVariable","display"],
                                                      ["INPUT","input"], 
                                                      ["OUTPUT","output"]
                                                    ]), "name")
          this.setInputsInline(true);
          this.setOutput(true, "Number");
          this.setColour(40);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          // this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
        }
      };

      Blockly.Blocks['set_system_variable'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendValueInput("right_hand_side")
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField('set')
              .appendField(new Blockly.FieldDropdown([
                                                      // ["systemVariable","display"],
                                                      ["INPUT","input"], 
                                                      ["OUTPUT","output"]
                                                    ]), "name")
              .appendField('to')
              .setCheck("Number");
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(40);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };


      Blockly.Blocks['set_output'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("set output")
              .appendField(new Blockly.FieldDropdown(self.robotOutputNames), "output_pin_name")
              .appendField('to')
              .appendField(new Blockly.FieldDropdown([
                                                      // ["outputPinStatus","display"],
                                                      ["ON","on"], 
                                                      ["OFF","off"]
                                                    ]), "out_state")
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(20);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };

      Blockly.Blocks['set_output_until'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("set output")
              .appendField(new Blockly.FieldDropdown(self.robotOutputNames), "output_pin_name")
              .appendField('to')
              .appendField(new Blockly.FieldDropdown([
                                                      // ["outputPinStatus","display"],
                                                      ["ON","on"],
                                                      ["OFF","off"]
                                                    ]), "out_state")
              .appendField("until")
              .appendField(new Blockly.FieldDropdown(self.robotInputNames), "input_pin_name")
              .appendField("=")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["inputPinStatus","display"],
                                                      ["ON","on"], 
                                                      ["OFF","off"]
                                                    ]), "input_state");
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(20);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };
  
      Blockly.Blocks['set_output_during'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("set output")
              .appendField(new Blockly.FieldDropdown(self.robotOutputNames), "output_pin_name")
              .appendField('to')
              .appendField(new Blockly.FieldDropdown([
                                                      // ["outputPinStatus","display"],
                                                      ["ON","on"], 
                                                      ["OFF","off"]
                                                    ]), "output_state")
              .appendField("during")
              .appendField(new Blockly.FieldDropdown(self.numberNames), "name")
              .appendField("msec")
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(20);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };
  
      Blockly.Blocks['wait_input'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("wait input until")
              .appendField(new Blockly.FieldDropdown(self.robotInputNames), "input_pin_name")
              .appendField("=")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["inputPinStatus","display"],
                                                      ["ON","on"], 
                                                      ["OFF","off"]
                                                    ]), "input_state");
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(20);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };
  
      Blockly.Blocks['moveL'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("moveL to")
              .appendField(new Blockly.FieldDropdown(self.options), "point_name_list")
              .appendField("with")
              .appendField(new Blockly.FieldDropdown([
                                                      ["X","enable"],
                                                      ["-","disable"], 
                                                    ]), "control_x")
              .appendField(new Blockly.FieldDropdown([
                                                      ["Y","enable"],
                                                      ["-","disable"], 
                                                    ]), "control_y")
              .appendField(new Blockly.FieldDropdown([
                                                      ["Z","enable"],
                                                      ["-","disable"], 
                                                    ]), "control_z")
              .appendField(new Blockly.FieldDropdown([
                                                      ["Rz","enable"],
                                                      ["-","disable"], 
                                                    ]), "control_rz")  
              .appendField(new Blockly.FieldDropdown([
                                                      ["Ry","enable"],
                                                      ["-","disable"], 
                                                    ]), "control_ry")                               
              .appendField(new Blockly.FieldDropdown([
                                                      ["Rx","enable"],
                                                      ["-","disable"], 
                                                    ]), "control_rx")

              .appendField(new Blockly.FieldDropdown([["no pallet","none"],
                                                      ["pallet No.1","1"], 
                                                      ["pallet No.2","2"], 
                                                      ["pallet No.3","3"], 
                                                      ["pallet No.4","4"], 
                                                      ["pallet No.5","5"], 
                                                      ["pallet No.6","6"], 
                                                      ["pallet No.7","7"], 
                                                      ["pallet No.8","8"], 
                                                      ["pallet No.9","9"], 
                                                      ["pallet No.10","10"], ]), "pallet_list")
              .appendField(new Blockly.FieldDropdown([["no camera","none"],
                                                      ["camera No.1","1"],
                                                      ["camera No.2","2"],
                                                      ["camera No.3","3"], 
                                                      ["camera No.4","4"], 
                                                      ["camera No.5","5"], 
                                                      ["camera No.6","6"], 
                                                      ["camera No.7","7"], 
                                                      ["camera No.8","8"], 
                                                      ["camera No.9","9"], 
                                                      ["camera No.10","10"]]), "camera_list");
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(20);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();          
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };

      Blockly.Blocks['moveP'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("moveP to")
              .appendField(new Blockly.FieldDropdown(self.options), "point_name_list")
              .appendField("with")
              .appendField(new Blockly.FieldDropdown([
                                                      ["X","enable"],
                                                      ["-","disable"], 
                                                    ]), "control_x")
              .appendField(new Blockly.FieldDropdown([
                                                      ["Y","enable"],
                                                      ["-","disable"], 
                                                    ]), "control_y")
              .appendField(new Blockly.FieldDropdown([
                                                      ["Z","enable"],
                                                      ["-","disable"], 
                                                    ]), "control_z")
              .appendField(new Blockly.FieldDropdown([
                                                      ["Rz","enable"],
                                                      ["-","disable"], 
                                                    ]), "control_rz")  
              .appendField(new Blockly.FieldDropdown([
                                                      ["Ry","enable"],
                                                      ["-","disable"], 
                                                    ]), "control_ry")                               
              .appendField(new Blockly.FieldDropdown([
                                                      ["Rx","enable"],
                                                      ["-","disable"], 
                                                    ]), "control_rx")

              .appendField(new Blockly.FieldDropdown([["no pallet","none"],
                                                      ["pallet No.1","1"], 
                                                      ["pallet No.2","2"], 
                                                      ["pallet No.3","3"], 
                                                      ["pallet No.4","4"], 
                                                      ["pallet No.5","5"], 
                                                      ["pallet No.6","6"], 
                                                      ["pallet No.7","7"], 
                                                      ["pallet No.8","8"], 
                                                      ["pallet No.9","9"], 
                                                      ["pallet No.10","10"], ]), "pallet_list")
              .appendField(new Blockly.FieldDropdown([["no camera","none"],
                                                      ["camera No.1","1"],
                                                      ["camera No.2","2"],
                                                      ["camera No.3","3"], 
                                                      ["camera No.4","4"], 
                                                      ["camera No.5","5"], 
                                                      ["camera No.6","6"], 
                                                      ["camera No.7","7"], 
                                                      ["camera No.8","8"], 
                                                      ["camera No.9","9"], 
                                                      ["camera No.10","10"]]), "camera_list");

          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(20);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();          
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };

      Blockly.Blocks['connect_external_io'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("connect to")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["deviceName","device_name"],
                                                      ["DIO000","DIO000"],
                                                      ["DIO001","DIO001"],
                                                      ["DIO002","DIO002"],
                                                      ["DIO003","DIO003"],
                                                      ["DIO004","DIO004"],
                                                      ["DIO005","DIO005"],
                                                    ]), "devive_name")
              .appendField("of")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["maker","maker"],
                                                      ["CONTEC","contec"],
                                                    ]), "external_maker")
              .appendField("as")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["IONo","IONo"],
                                                      ["IO\nNo.1","1"],
                                                      ["IO\nNo.2","2"],
                                                      ["IO\nNo.3","3"], 
                                                      ["IO\nNo.4","4"], 
                                                      ["IO\nNo.5","5"], 
                                                      ["IO\nNo.6","6"], 
                                                      ["IO\nNo.7","7"], 
                                                      ["IO\nNo.8","8"], 
                                                      ["IO\nNo.9","9"], 
                                                      ["IO\nNo.10","10"]
                                                    ]), "io_no");
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(60);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };

      Blockly.Blocks['wait_external_io_input'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("wait")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["IONo","IONo"],
                                                      ["IO\nNo.1","1"],
                                                      ["IO\nNo.2","2"],
                                                      ["IO\nNo.3","3"], 
                                                      ["IO\nNo.4","4"], 
                                                      ["IO\nNo.5","5"], 
                                                      ["IO\nNo.6","6"], 
                                                      ["IO\nNo.7","7"], 
                                                      ["IO\nNo.8","8"], 
                                                      ["IO\nNo.9","9"], 
                                                      ["IO\nNo.10","10"]
                                                    ]), "io_no")
              .appendField("input until")
              .appendField(new Blockly.FieldDropdown(self.externalInputNames), "input_pin_name")
              // .appendField(new Blockly.FieldDropdown([
              //                                         // ["inputPinName","display"],
              //                                         ["DI_0","0"],
              //                                         ["DI_1","1"],
              //                                         ["DI_2","2"],
              //                                         ["DI_3","3"],
              //                                         ["DI_4","4"],
              //                                         ["DI_5","5"],
              //                                         ["DI_6","6"],
              //                                         ["DI_7","7"],
              //                                         ["DI_8","8"],
              //                                         ["DI_9","9"],
              //                                         ["DI_10","10"],
              //                                         ["DI_11","11"],
              //                                         ["DI_12","12"],
              //                                         ["DI_13","13"],
              //                                         ["DI_14","14"],
              //                                         ["DI_15","15"],
              //                                       ]), "input_pin_name")
              .appendField("=")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["inputPinStatus","display"],
                                                      ["ON","on"], 
                                                      ["OFF","off"]
                                                    ]), "in_state");
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(60);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };

      Blockly.Blocks['set_external_io_output'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("set")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["IONo","IONo"],
                                                      ["IO\nNo.1","1"],
                                                      ["IO\nNo.2","2"],
                                                      ["IO\nNo.3","3"], 
                                                      ["IO\nNo.4","4"], 
                                                      ["IO\nNo.5","5"], 
                                                      ["IO\nNo.6","6"], 
                                                      ["IO\nNo.7","7"], 
                                                      ["IO\nNo.8","8"], 
                                                      ["IO\nNo.9","9"], 
                                                      ["IO\nNo.10","10"]
                                                    ]), "io_no")
              .appendField("output")
              .appendField(new Blockly.FieldDropdown(self.externalOutputNames), "output_pin_name")
              // .appendField(new Blockly.FieldDropdown([
              //                                         // ["outputPinName","display"],
              //                                         ["DO_0","0"],
              //                                         ["DO_1","1"],
              //                                         ["DO_2","2"],
              //                                         ["DO_3","3"],
              //                                         ["DO_4","4"],
              //                                         ["DO_5","5"],
              //                                         ["DO_6","6"],
              //                                         ["DO_7","7"],
              //                                         ["DO_8","8"],
              //                                         ["DO_9","9"],
              //                                         ["DO_10","10"],
              //                                         ["DO_11","11"],
              //                                         ["DO_12","12"],
              //                                         ["DO_13","13"],
              //                                         ["DO_14","14"],
              //                                         ["DO_15","15"],
              //                                        ]), "out_pin_no")
              .appendField('to')
              .appendField(new Blockly.FieldDropdown([
                                                      // ["outputPinStatus","display"],
                                                      ["ON","on"], 
                                                      ["OFF","off"]
                                                    ]), "out_state")
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(60);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };

      Blockly.Blocks['set_external_io_output_upon'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendValueInput("condition")
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("set")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["IONo","IONo"],
                                                      ["IO\nNo.1","1"],
                                                      ["IO\nNo.2","2"],
                                                      ["IO\nNo.3","3"], 
                                                      ["IO\nNo.4","4"], 
                                                      ["IO\nNo.5","5"], 
                                                      ["IO\nNo.6","6"], 
                                                      ["IO\nNo.7","7"], 
                                                      ["IO\nNo.8","8"], 
                                                      ["IO\nNo.9","9"], 
                                                      ["IO\nNo.10","10"]
                                                    ]), "io_no")
              .appendField("output")
              .appendField(new Blockly.FieldDropdown(self.externalOutputNames), "output_pin_name")
              // .appendField(new Blockly.FieldDropdown([
              //                                         // ["outputPinName","display"],
              //                                         ["DO_0","0"],
              //                                         ["DO_1","1"],
              //                                         ["DO_2","2"],
              //                                         ["DO_3","3"],
              //                                         ["DO_4","4"],
              //                                         ["DO_5","5"],
              //                                         ["DO_6","6"],
              //                                         ["DO_7","7"],
              //                                         ["DO_8","8"],
              //                                         ["DO_9","9"],
              //                                         ["DO_10","10"],
              //                                         ["DO_11","11"],
              //                                         ["DO_12","12"],
              //                                         ["DO_13","13"],
              //                                         ["DO_14","14"],
              //                                         ["DO_15","15"],
              //                                        ]), "out_pin_no")
              .appendField('to')
              .appendField(new Blockly.FieldDropdown([
                                                      // ["outputPinStatus","display"],
                                                      ["ON","on"], 
                                                      ["OFF","off"],
                                                      ["100msec","100msec"],
                                                      ["200msec","200msec"],
                                                      ["500msec","500msec"],
                                                      ["1000msec","1000msec"],
                                                      // ["2000msec","2000msec"],
                                                      // ["3000msec","3000msec"],
                                                    ]), "out_state")
              .appendField("upon")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["triggerCondition","display"],
                                                      ["―","steady"],
                                                      ["↑","rising"],
                                                      ["↓","falling"],
                                                    ]), "trigger_condition")
              .setCheck("Boolean");
          this.setPreviousStatement(true, "event");
          this.setNextStatement(true, "event");
          this.setColour(60);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };


      Blockly.Blocks['set_external_io_output_until'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("set")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["IONo","IONo"],
                                                      ["IO\nNo.1","1"],
                                                      ["IO\nNo.2","2"],
                                                      ["IO\nNo.3","3"], 
                                                      ["IO\nNo.4","4"], 
                                                      ["IO\nNo.5","5"], 
                                                      ["IO\nNo.6","6"], 
                                                      ["IO\nNo.7","7"], 
                                                      ["IO\nNo.8","8"], 
                                                      ["IO\nNo.9","9"], 
                                                      ["IO\nNo.10","10"]
                                                    ]), "io_no")
              .appendField("output")
              .appendField(new Blockly.FieldDropdown(self.externalOutputNames), "output_pin_name")
              // .appendField(new Blockly.FieldDropdown([
              //                                         // ["outputPinName","display"],
              //                                         ["DO_0","0"],
              //                                         ["DO_1","1"],
              //                                         ["DO_2","2"],
              //                                         ["DO_3","3"],
              //                                         ["DO_4","4"],
              //                                         ["DO_5","5"],
              //                                         ["DO_6","6"],
              //                                         ["DO_7","7"],
              //                                         ["DO_8","8"],
              //                                         ["DO_9","9"],
              //                                         ["DO_10","10"],
              //                                         ["DO_11","11"],
              //                                         ["DO_12","12"],
              //                                         ["DO_13","13"],
              //                                         ["DO_14","14"],
              //                                         ["DO_15","15"],
              //                                        ]), "out_pin_no")
              .appendField('to')
              .appendField(new Blockly.FieldDropdown([
                                                      // ["outputPinStatus","display"],
                                                      ["ON","on"], 
                                                      ["OFF","off"]
                                                    ]), "out_state")
              .appendField("until")
              .appendField(new Blockly.FieldDropdown(self.externalInputNames), "input_pin_name")
              // .appendField(new Blockly.FieldDropdown([
              //                                         // ["inputPinName","display"],
              //                                         ["DI_0","0"],
              //                                         ["DI_1","1"],
              //                                         ["DI_2","2"],
              //                                         ["DI_3","3"],
              //                                         ["DI_4","4"],
              //                                         ["DI_5","5"],
              //                                         ["DI_6","6"],
              //                                         ["DI_7","7"],
              //                                         ["DI_8","8"],
              //                                         ["DI_9","9"],
              //                                         ["DI_10","10"],
              //                                         ["DI_11","11"],
              //                                         ["DI_12","12"],
              //                                         ["DI_13","13"],
              //                                         ["DI_14","14"],
              //                                         ["DI_15","15"],
              //                                       ]), "input_pin_name")
              .appendField("=")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["inputPinStatus","display"],
                                                      ["ON","on"], 
                                                      ["OFF","off"]
                                                    ]), "in_state");
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(60);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };
  
      Blockly.Blocks['set_external_io_output_during'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("set")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["IONo","IONo"],
                                                      ["IO\nNo.1","1"],
                                                      ["IO\nNo.2","2"],
                                                      ["IO\nNo.3","3"], 
                                                      ["IO\nNo.4","4"], 
                                                      ["IO\nNo.5","5"], 
                                                      ["IO\nNo.6","6"], 
                                                      ["IO\nNo.7","7"], 
                                                      ["IO\nNo.8","8"], 
                                                      ["IO\nNo.9","9"], 
                                                      ["IO\nNo.10","10"]
                                                    ]), "io_no")
              .appendField("output")
              .appendField(new Blockly.FieldDropdown(self.externalOutputNames), "output_pin_name")
              // .appendField(new Blockly.FieldDropdown([
              //                                         // ["outputPinName","display"],
              //                                         ["DO_0","0"],
              //                                         ["DO_1","1"],
              //                                         ["DO_2","2"],
              //                                         ["DO_3","3"],
              //                                         ["DO_4","4"],
              //                                         ["DO_5","5"],
              //                                         ["DO_6","6"],
              //                                         ["DO_7","7"],
              //                                         ["DO_8","8"],
              //                                         ["DO_9","9"],
              //                                         ["DO_10","10"],
              //                                         ["DO_11","11"],
              //                                         ["DO_12","12"],
              //                                         ["DO_13","13"],
              //                                         ["DO_14","14"],
              //                                         ["DO_15","15"],
              //                                        ]), "out_pin_no")
              .appendField('to')
              .appendField(new Blockly.FieldDropdown([
                                                      // ["outputPinStatus","display"],
                                                      ["ON","on"], 
                                                      ["OFF","off"]
                                                    ]), "out_state")
              .appendField("during")
              .appendField(new Blockly.FieldDropdown(self.numberNames), "name")
              .appendField("msec")
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(60);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };

      Blockly.Blocks['external_io'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type; 
          this.hasBlockNo = false; 
          this.hasBlockFlow = false; 
          this.appendDummyInput()
          .appendField(new Blockly.FieldDropdown([
                                                  // ["IONo","IONo"],
                                                  ["IO\nNo.1","1"],
                                                  ["IO\nNo.2","2"],
                                                  ["IO\nNo.3","3"], 
                                                  ["IO\nNo.4","4"], 
                                                  ["IO\nNo.5","5"], 
                                                  ["IO\nNo.6","6"], 
                                                  ["IO\nNo.7","7"], 
                                                  ["IO\nNo.8","8"], 
                                                  ["IO\nNo.9","9"], 
                                                  ["IO\nNo.10","10"]
                                                ]), "io_no")
            // .appendField(new Blockly.FieldDropdown([["inputPinName","display"]],), "input_pin_name")
                                                
          .appendField(new Blockly.FieldDropdown(self.externalInputNames), "input_pin_name")
          // .appendField(new Blockly.FieldDropdown([
          //                                         // ["inputPinName","display"],
          //                                         ["DI_0","0"],
          //                                         ["DI_1","1"],
          //                                         ["DI_2","2"],
          //                                         ["DI_3","3"],
          //                                         ["DI_4","4"],
          //                                         ["DI_5","5"],
          //                                         ["DI_6","6"],
          //                                         ["DI_7","7"],
          //                                         ["DI_8","8"],
          //                                         ["DI_9","9"],
          //                                         ["DI_10","10"],
          //                                         ["DI_11","11"],
          //                                         ["DI_12","12"],
          //                                         ["DI_13","13"],
          //                                         ["DI_14","14"],
          //                                         ["DI_15","15"],
          //                                       ]), "input_pin_name")
          this.setInputsInline(true);
          this.setOutput(true, "Boolean");
          this.setColour(60);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
        }
      };

      Blockly.Blocks['raise_error'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("raise error with the message")
          // this.appendEndRowInput()
              // .appendField(", display")
              .appendField(new Blockly.FieldTextInput("errorMessage"), "error_message")
              // .appendField("if found");
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(360);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        },
      };

      Blockly.Blocks['raise_error_upon'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendValueInput("condition")
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("raise error with the message")
              // .appendField(new Blockly.FieldDropdown([
              //   ["error1","1"], ["error2","2"], ["error3","3"], ["error4","4"], ["error5","5"],
              //   ["error6","6"], ["error7","7"], ["error8","8"], ["error9","9"], ["error10","10"],
              //   ["error11","11"], ["error12","12"], ["error13","13"], ["error14","14"], ["error15","15"],
              //   ["error16","16"], ["error17","17"], ["error18","18"], ["error19","19"], ["error20","20"],
              //   ["error21","21"], ["error22","22"], ["error23","23"], ["error24","24"], ["error25","25"],
              //   ["error26","26"], ["error27","27"], ["error28","28"], ["error29","29"], ["error30","30"],
              //   ["error31","31"], ["error32","32"], ["error33","33"], ["error34","34"], ["error35","35"],
              //   ["error36","36"], ["error37","37"], ["error38","38"], ["error39","39"], ["error40","40"],
              //   ["error41","41"], ["error42","42"], ["error43","43"], ["error44","44"], ["error45","45"],
              //   ["error46","46"], ["error47","47"], ["error48","48"], ["error49","49"], ["error50","50"],
              //   ["error51","51"], ["error52","52"], ["error53","53"], ["error54","54"], ["error55","55"],
              //   ["error56","56"], ["error57","57"], ["error58","58"], ["error59","59"], ["error60","60"],
              //   ["error61","61"], ["error62","62"], ["error63","63"], ["error64","64"], ["error65","65"],
              //   ["error66","66"], ["error67","67"], ["error68","68"], ["error69","69"], ["error70","70"],
              //   ["error71","71"], ["error72","72"], ["error73","73"], ["error74","74"], ["error75","75"],
              //   ["error76","76"], ["error77","77"], ["error78","78"], ["error79","79"], ["error80","80"],
              //   ["error81","81"], ["error82","82"], ["error83","83"], ["error84","84"], ["error85","85"],
              //   ["error86","86"], ["error87","87"], ["error88","88"], ["error89","89"], ["error90","90"],
              //   ["error91","91"], ["error92","92"], ["error93","93"], ["error94","94"], ["error95","95"],
              //   ["error96","96"], ["error97","97"], ["error98","98"], ["error99","99"], ["error100","100"]
              // ]), "error_list")     
              // .appendField("with");
          // this.appendEndRowInput()
              // .appendField(", display")
              .appendField(new Blockly.FieldTextInput("errorMessage"), "error_message")
          // this.appendValueInput('')
              .appendField("upon")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["triggerCondition","display"],
                                                      ["―","steady"],
                                                      ["↑","rising"],
                                                      ["↓","falling"],
                                                    ]), "trigger_condition")
              .setCheck("Boolean");
          this.setPreviousStatement(true, "event");
          this.setNextStatement(true, "event");
          this.setColour(360);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        },
      };

      Blockly.Blocks['wait_block'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          // this.appendDummyInput()
          this.appendValueInput("condition")
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("wait until") 
          // this.appendValueInput("condition")
              .setCheck("Boolean");
          // this.appendEndRowInput()
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(200);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        },
      };

      Blockly.Blocks['return'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("return to loop start");
          this.setPreviousStatement(true, "process");
          this.setColour(40);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };
  
      Blockly.Blocks['select_robot'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField("select robot:")
              .appendField(new Blockly.FieldTextInput(`${self.robotName}`), "robotName");
              // .appendField(`${self.robotName}`);
          // this.appendEndRowInput()
          //     .appendField(new Blockly.FieldDropdown([["IAI 3AXIS-TABLETOP","iai_3axis_tabletop"],
          //                                             ["IAI 4AXIS-TABLETOP","iai_4axis_tabletop"],
          //                                             ["Dobot MG400","dobot_mg400"],
          //                                             ["YAMAHA SCARA","yamaha_scara"]]), "robot_name_list")
          //     .appendField("as robot");              
          this.setNextStatement(true, "process");
          this.setColour(20);
          this.setTooltip("");
          this.setHelpUrl("");
          this.setEditable(false);
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        },
      };
      
      Blockly.Blocks['stop_robot_upon'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendValueInput("condition")
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("stop robot")
              .appendField("upon")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["triggerCondition","display"],
                                                      ["―","steady"],
                                                      ["↑","rising"],
                                                      ["↓","falling"],
                                                    ]), "trigger_condition")
              .setCheck("Boolean");
          this.setPreviousStatement(true, "event");
          this.setNextStatement(true, "event");
          this.setColour(20);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        },
      };

      Blockly.Blocks['connect_camera'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("connect to")
              // .appendField(new Blockly.FieldTextInput("octetNo1"), "octet1")
              .appendField(new Blockly.FieldNumber(127), "octet1")
              // .appendField(new Blockly.FieldNumber(192), "octet1")
              .appendField(".")
              // .appendField(new Blockly.FieldTextInput("octetNo2"), "octet2")
              .appendField(new Blockly.FieldNumber(0), "octet2")
              // .appendField(new Blockly.FieldNumber(168), "octet2")
              .appendField(".")
              // .appendField(new Blockly.FieldTextInput("octetNo3"), "octet3")
              .appendField(new Blockly.FieldNumber(0), "octet3")
              // .appendField(new Blockly.FieldNumber(250), "octet3")
              .appendField(".")
              // .appendField(new Blockly.FieldTextInput("octetNo4"), "octet4")
              .appendField(new Blockly.FieldNumber(1), "octet4")
              // .appendField(new Blockly.FieldNumber(99), "octet4")
              .appendField(":")
              // .appendField(new Blockly.FieldTextInput("portNo"), "portNo")
              .appendField(new Blockly.FieldNumber(5000), "port");
              // .appendField(new Blockly.FieldNumber(7930), "port");
              this.appendEndRowInput()
              // .appendField(new Blockly.FieldDropdown([["Facilea","facilea"],
              //                                         ["Vision Master","vision_master"],
              //                                         ["VAST","vast"]]), "camera_name_list")
              .appendField("as")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["cameraNo","cameraNo"],
                                                      ["camera\nNo.1","1"],
                                                      ["camera\nNo.2","2"],
                                                      ["camera\nNo.3","3"], 
                                                      ["camera\nNo.4","4"], 
                                                      ["camera\nNo.5","5"], 
                                                      ["camera\nNo.6","6"], 
                                                      ["camera\nNo.7","7"], 
                                                      ["camera\nNo.8","8"], 
                                                      ["camera\nNo.9","9"], 
                                                      ["camera\nNo.10","10"]]), "camera_list");
              
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(90);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        },
      };

      Blockly.Blocks['run_camera_wait'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("run")
              .appendField(new Blockly.FieldDropdown([
                // ["cameraNo","cameraNo"],
                ["camera\nNo.1","1"],
                ["camera\nNo.2","2"],
                ["camera\nNo.3","3"], 
                ["camera\nNo.4","4"], 
                ["camera\nNo.5","5"], 
                ["camera\nNo.6","6"], 
                ["camera\nNo.7","7"], 
                ["camera\nNo.8","8"], 
                ["camera\nNo.9","9"], 
                ["camera\nNo.10","10"]]
              ), "camera_list")
              .appendField("with")
              .appendField(new Blockly.FieldDropdown([
                // ["programNo", "programNo"],
                ["program\nNo.1","1"], ["program\nNo.2","2"], ["program\nNo.3","3"], ["program\nNo.4","4"], ["program\nNo.5","5"],
                ["program\nNo.6","6"], ["program\nNo.7","7"], ["program\nNo.8","8"], ["program\nNo.9","9"], ["program\nNo.10","10"],
                ["program\nNo.11","11"], ["program\nNo.12","12"], ["program\nNo.13","13"], ["program\nNo.14","14"], ["program\nNo.15","15"],
                ["program\nNo.16","16"], ["program\nNo.17","17"], ["program\nNo.18","18"], ["program\nNo.19","19"], ["program\nNo.20","20"],
                ["program\nNo.21","21"], ["program\nNo.22","22"], ["program\nNo.23","23"], ["program\nNo.24","24"], ["program\nNo.25","25"],
                ["program\nNo.26","26"], ["program\nNo.27","27"], ["program\nNo.28","28"], ["program\nNo.29","29"], ["program\nNo.30","30"],
                ["program\nNo.31","31"], ["program\nNo.32","32"], ["program\nNo.33","33"], ["program\nNo.34","34"], ["program\nNo.35","35"],
                ["program\nNo.36","36"], ["program\nNo.37","37"], ["program\nNo.38","38"], ["program\nNo.39","39"], ["program\nNo.40","40"],
                ["program\nNo.41","41"], ["program\nNo.42","42"], ["program\nNo.43","43"], ["program\nNo.44","44"], ["program\nNo.45","45"],
                ["program\nNo.46","46"], ["program\nNo.47","47"], ["program\nNo.48","48"], ["program\nNo.49","49"], ["program\nNo.50","50"],
                ["program\nNo.51","51"], ["program\nNo.52","52"], ["program\nNo.53","53"], ["program\nNo.54","54"], ["program\nNo.55","55"],
                ["program\nNo.56","56"], ["program\nNo.57","57"], ["program\nNo.58","58"], ["program\nNo.59","59"], ["program\nNo.60","60"],
                ["program\nNo.61","61"], ["program\nNo.62","62"], ["program\nNo.63","63"], ["program\nNo.64","64"], ["program\nNo.65","65"],
                ["program\nNo.66","66"], ["program\nNo.67","67"], ["program\nNo.68","68"], ["program\nNo.69","69"], ["program\nNo.70","70"],
                ["program\nNo.71","71"], ["program\nNo.72","72"], ["program\nNo.73","73"], ["program\nNo.74","74"], ["program\nNo.75","75"],
                ["program\nNo.76","76"], ["program\nNo.77","77"], ["program\nNo.78","78"], ["program\nNo.79","79"], ["program\nNo.80","80"],
                ["program\nNo.81","81"], ["program\nNo.82","82"], ["program\nNo.83","83"], ["program\nNo.84","84"], ["program\nNo.85","85"],
                ["program\nNo.86","86"], ["program\nNo.87","87"], ["program\nNo.88","88"], ["program\nNo.89","89"], ["program\nNo.90","90"],
                ["program\nNo.91","91"], ["program\nNo.92","92"], ["program\nNo.93","93"], ["program\nNo.94","94"], ["program\nNo.95","95"],
                ["program\nNo.96","96"], ["program\nNo.97","97"], ["program\nNo.98","98"], ["program\nNo.99","99"], ["program\nNo.100","100"]
              ]), "program_list")              
              .appendField("waiting for the result");
              
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(90);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        },
      };

      Blockly.Blocks['run_camera'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("run")
              .appendField(new Blockly.FieldDropdown([
                // ["cameraNo","cameraNo"],
                ["camera\nNo.1","1"],
                ["camera\nNo.2","2"],
                ["camera\nNo.3","3"], 
                ["camera\nNo.4","4"], 
                ["camera\nNo.5","5"], 
                ["camera\nNo.6","6"], 
                ["camera\nNo.7","7"], 
                ["camera\nNo.8","8"], 
                ["camera\nNo.9","9"], 
                ["camera\nNo.10","10"]]
              ), "camera_list")
              .appendField("with")
              .appendField(new Blockly.FieldDropdown([
                // ["programNo", "programNo"],
                ["program\nNo.1","1"], ["program\nNo.2","2"], ["program\nNo.3","3"], ["program\nNo.4","4"], ["program\nNo.5","5"],
                ["program\nNo.6","6"], ["program\nNo.7","7"], ["program\nNo.8","8"], ["program\nNo.9","9"], ["program\nNo.10","10"],
                ["program\nNo.11","11"], ["program\nNo.12","12"], ["program\nNo.13","13"], ["program\nNo.14","14"], ["program\nNo.15","15"],
                ["program\nNo.16","16"], ["program\nNo.17","17"], ["program\nNo.18","18"], ["program\nNo.19","19"], ["program\nNo.20","20"],
                ["program\nNo.21","21"], ["program\nNo.22","22"], ["program\nNo.23","23"], ["program\nNo.24","24"], ["program\nNo.25","25"],
                ["program\nNo.26","26"], ["program\nNo.27","27"], ["program\nNo.28","28"], ["program\nNo.29","29"], ["program\nNo.30","30"],
                ["program\nNo.31","31"], ["program\nNo.32","32"], ["program\nNo.33","33"], ["program\nNo.34","34"], ["program\nNo.35","35"],
                ["program\nNo.36","36"], ["program\nNo.37","37"], ["program\nNo.38","38"], ["program\nNo.39","39"], ["program\nNo.40","40"],
                ["program\nNo.41","41"], ["program\nNo.42","42"], ["program\nNo.43","43"], ["program\nNo.44","44"], ["program\nNo.45","45"],
                ["program\nNo.46","46"], ["program\nNo.47","47"], ["program\nNo.48","48"], ["program\nNo.49","49"], ["program\nNo.50","50"],
                ["program\nNo.51","51"], ["program\nNo.52","52"], ["program\nNo.53","53"], ["program\nNo.54","54"], ["program\nNo.55","55"],
                ["program\nNo.56","56"], ["program\nNo.57","57"], ["program\nNo.58","58"], ["program\nNo.59","59"], ["program\nNo.60","60"],
                ["program\nNo.61","61"], ["program\nNo.62","62"], ["program\nNo.63","63"], ["program\nNo.64","64"], ["program\nNo.65","65"],
                ["program\nNo.66","66"], ["program\nNo.67","67"], ["program\nNo.68","68"], ["program\nNo.69","69"], ["program\nNo.70","70"],
                ["program\nNo.71","71"], ["program\nNo.72","72"], ["program\nNo.73","73"], ["program\nNo.74","74"], ["program\nNo.75","75"],
                ["program\nNo.76","76"], ["program\nNo.77","77"], ["program\nNo.78","78"], ["program\nNo.79","79"], ["program\nNo.80","80"],
                ["program\nNo.81","81"], ["program\nNo.82","82"], ["program\nNo.83","83"], ["program\nNo.84","84"], ["program\nNo.85","85"],
                ["program\nNo.86","86"], ["program\nNo.87","87"], ["program\nNo.88","88"], ["program\nNo.89","89"], ["program\nNo.90","90"],
                ["program\nNo.91","91"], ["program\nNo.92","92"], ["program\nNo.93","93"], ["program\nNo.94","94"], ["program\nNo.95","95"],
                ["program\nNo.96","96"], ["program\nNo.97","97"], ["program\nNo.98","98"], ["program\nNo.99","99"], ["program\nNo.100","100"]
              ]), "program_list")              
              
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(90);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        },
      };

      Blockly.Blocks['wait_camera'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("wait for the result of")
              .appendField(new Blockly.FieldDropdown([
                // ["cameraNo","cameraNo"],
                ["camera\nNo.1","1"],
                ["camera\nNo.2","2"],
                ["camera\nNo.3","3"], 
                ["camera\nNo.4","4"], 
                ["camera\nNo.5","5"], 
                ["camera\nNo.6","6"], 
                ["camera\nNo.7","7"], 
                ["camera\nNo.8","8"], 
                ["camera\nNo.9","9"], 
                ["camera\nNo.10","10"]]
              ), "camera_list")
              
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(90);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        },
      };

      Blockly.Blocks['start_thread'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true;
          // this.appendDummyInput()
          this.appendValueInput("condition")
              // .appendField("管理ブロック")
              .appendField("start thread with")
          // this.appendValueInput('condition')
              .setCheck("Boolean");
          this.appendStatementInput("DO")
              .setCheck("process");
              // .setCheck(null);
          this.setInputsInline(false);
          this.setNextStatement(false, null);
          this.setColour(200);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          // this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          // self.addTimeoutOption(this);
        }
      };

      Blockly.Blocks['create_event'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true;
          this.appendDummyInput()
              .appendField("create event trigger")
          this.appendStatementInput("EVENT")
              .setCheck("event");
          this.setInputsInline(false);
          this.setNextStatement(false, null);
          this.setColour(200);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          // this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          // self.addTimeoutOption(this);
        },
      };

      Blockly.Blocks['loop'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField("loop");
          this.appendStatementInput("DO")
              .setCheck(null);
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(false, null);
          this.setColour(40);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          // this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          // self.addTimeoutOption(this);
        }
      };
  
      Blockly.Blocks['set_motor'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField("set motor ")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["motorStatus","display"], 
                                                      ["ON","on"], 
                                                      ["OFF","off"]
                                                    ]), "state_list");
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(20);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };
   
      Blockly.Blocks['origin'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField("move origin");
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(20);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };
  
      Blockly.Blocks['set_pallet'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("set")
              // .appendField("row:")
              .appendField("(")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["rowCount","rowCount"],
                                                      ["row=2","2"],
                                                      ["row=3","3"],
                                                      ["row=4","4"],
                                                      ["row=5","5"],
                                                      ["row=6","6"],
                                                      ["row=7","7"],
                                                      ["row=8","8"],
                                                      ["row=9","9"],
                                                      ["row=10","10"]]), "row_list")
              // .appendField("col:")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["colCount","colCount"],
                                                      ["col=2","2"],
                                                      ["col=3","3"],
                                                      ["col=4","4"],
                                                      ["col=5","5"],
                                                      ["col=6","6"],
                                                      ["col=7","7"],
                                                      ["col=8","8"],
                                                      ["col=9","9"],
                                                      ["col=10","10"]]), "col_list")
              .appendField(",")
              .appendField("A=")
              // .appendField(new Blockly.FieldDropdown([["cornerPointA","cornerPointA"],]), "cornerPointA")
              .appendField(new Blockly.FieldDropdown(self.options), "A_name_list")
              .appendField("B=")
              // .appendField(new Blockly.FieldDropdown([["cornerPointB","cornerPointB"],]), "cornerPointB")
              .appendField(new Blockly.FieldDropdown(self.options), "B_name_list")
              .appendField("C=")
              // .appendField(new Blockly.FieldDropdown([["cornerPointC","cornerPointC"],]), "cornerPointC")
              .appendField(new Blockly.FieldDropdown(self.options), "C_name_list")
              .appendField("D=")
              // .appendField(new Blockly.FieldDropdown([["cornerPointD","cornerPointD"],]), "cornerPointD")
              .appendField(new Blockly.FieldDropdown(self.options), "D_name_list")
              .appendField(")")
              .appendField("for")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["usage","usage"], 
                                                      ["pick","max"], 
                                                      ["place","zero"],
                                                    ]), "reseted_value")
              .appendField("on")
              // .appendField("No.:")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["palletNo","palletNo"], 
                                                      ["pallet\nNo.1","1"], 
                                                      ["pallet\nNo.2","2"],
                                                      ["pallet\nNo.3","3"],
                                                      ["pallet\nNo.4","4"],
                                                      ["pallet\nNo.5","5"],
                                                      ["pallet\nNo.6","6"],
                                                      ["pallet\nNo.7","7"],
                                                      ["pallet\nNo.8","8"],
                                                      ["pallet\nNo.9","9"],
                                                      ["pallet\nNo.10","10"]]), "no_list");
           this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(260);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };
  
      Blockly.Blocks['move_next_pallet'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("move on to next pocket in")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["palletNo","palletNo"], 
                                                      ["pallet\nNo.1","1"], 
                                                      ["pallet\nNo.2","2"],
                                                      ["pallet\nNo.3","3"],
                                                      ["pallet\nNo.4","4"],
                                                      ["pallet\nNo.5","5"],
                                                      ["pallet\nNo.6","6"],
                                                      ["pallet\nNo.7","7"],
                                                      ["pallet\nNo.8","8"],
                                                      ["pallet\nNo.9","9"],
                                                      ["pallet\nNo.10","10"]]), "no_list")
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(260);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };
  
      Blockly.Blocks['reset_pallet'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("reset")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["palletNo","palletNo"], 
                                                      ["pallet\nNo.1","1"], 
                                                      ["pallet\nNo.2","2"],
                                                      ["pallet\nNo.3","3"],
                                                      ["pallet\nNo.4","4"],
                                                      ["pallet\nNo.5","5"],
                                                      ["pallet\nNo.6","6"],
                                                      ["pallet\nNo.7","7"],
                                                      ["pallet\nNo.8","8"],
                                                      ["pallet\nNo.9","9"],
                                                      ["pallet\nNo.10","10"]]), "no_list")
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(260);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };
   
      Blockly.Blocks['math_custom_number'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type; 
          this.hasBlockNo = false; 
          this.hasBlockFlow = false; 
          this.appendDummyInput()
              .appendField(new Blockly.FieldDropdown(self.numberNames), "name")
          this.setInputsInline(true);
          this.setOutput(true, "Number");
          this.setColour(160);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
        }
      };

      Blockly.Blocks['set_number'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendValueInput("right_hand_side")
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField('set')
              .appendField(new Blockly.FieldDropdown(self.numberNames), "name")
              .appendField('to')
              .setCheck("Number");
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(160);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };

      Blockly.Blocks['set_number_upon'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendValueInput("right_hand_side")
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField('set')
              .appendField(new Blockly.FieldDropdown(self.numberNames), "name")
              .appendField('to')
              .setCheck("Number");
          this.appendValueInput("condition")
              .appendField("upon")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["triggerCondition","display"],
                                                      ["―","steady"],
                                                      ["↑","rising"],
                                                      ["↓","falling"],
                                                    ]), "trigger_condition")
              .setCheck("Boolean");
          this.setInputsInline(true);
          this.setPreviousStatement(true, "event");
          this.setNextStatement(true, "event");
          this.setColour(160);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        },
      };

      Blockly.Blocks['set_flag'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendValueInput("right_hand_side")
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField('set')
              .appendField(new Blockly.FieldDropdown(self.flagNames), "name")
              .appendField('to')
              .setCheck("Boolean");
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(200);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };

      Blockly.Blocks['set_flag_upon'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendValueInput("right_hand_side")
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField('set')
              .appendField(new Blockly.FieldDropdown(self.flagNames), "name")
              .appendField('to')
              .setCheck("Boolean");
          this.appendValueInput("condition")
              .appendField("upon")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["triggerCondition","display"],
                                                      ["―","steady"],
                                                      ["↑","rising"],
                                                      ["↓","falling"],
                                                    ]), "trigger_condition")
              .setCheck("Boolean");
          this.setInputsInline(true);
          this.setPreviousStatement(true, "event");
          this.setNextStatement(true, "event");
          this.setColour(200);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };


      Blockly.Blocks['logic_block'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = false; 
          this.hasBlockFlow = false; 
          this.appendDummyInput()
              // .appendField('No:')
              // .appendField('type:')
              .appendField(new Blockly.FieldDropdown([
                                                      // ["blockName","blockName"], 
                                                      ["moveL","moveL"], 
                                                      ["moveP","moveP"], 
                                                      ["run camera","run_camera"],
                                                      ["run camera wait","run_camera_wait"],
                                                      ["wait timer","wait_timer"],
                                                      ["wait block","wait_block"],
                                                      ["wait input","wait_input"],
                                                      ["set flag","set_flag"],
                                                      ["set number","set_number"],
                                                      ["set output","set_output"],
                                                      ["set output during","set_output_during"],
                                                      ["set output wait","set_output_until"],
                                                      ["set external io output","set_external_io_output"],
                                                      ["set external io output until","set_external_io_output_until"],
                                                      ["set external io output during","set_external_io_output_during"],
                                                      ["set plc bit","set_plc_bit"],
                                                      ["set plc bit during","set_plc_bit_during"],
                                                      ["set plc bit wait","set_plc_bit_until"],
                                                    ]), "block_type")
                      
                .appendField('@')
                // .appendField(new Blockly.FieldDropdown([
                //                                         ["blockNo","blockNo"], 
                //                                       ]), "no")
                .appendField(new Blockly.FieldDropdown(Array.from({ length: 100 }, (_, i) => [String(i + 1), String(i + 1)])), "block_no")
                .appendField(new Blockly.FieldDropdown([
                                                        // ["action","action"], 
                                                        ["start","start"], 
                                                        ["stop","stop"]
                                                      ]), "block_status")
          this.setInputsInline(true);
          this.setOutput(true, "Boolean");
          this.setColour(200);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };

      Blockly.Blocks['condition_display'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = false; 
          this.hasBlockFlow = false; 
          this.appendDummyInput()
                .appendField('condition')
          this.setInputsInline(true);
          this.setOutput(true, "Boolean");
          this.setColour(200);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };

      Blockly.Blocks['robot_io'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type; 
          this.hasBlockNo = false; 
          this.hasBlockFlow = false; 
          this.appendDummyInput()
              // .appendField("wait input until")
              .appendField(new Blockly.FieldDropdown(self.robotInputNames), "input_pin_name")
          this.setInputsInline(true);
          this.setOutput(true, "Boolean");
          this.setColour(20);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
        }
      };

      Blockly.Blocks['robot_position'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type; 
          this.hasBlockNo = false; 
          this.hasBlockFlow = false; 
          this.appendDummyInput()
              .appendField("current position")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["axisName","axis_name"], 
                                                      ["X","x"], 
                                                      ["Y","y"],
                                                      ["Z","z"],
                                                      ["Rx","rx"],
                                                      ["Ry","ry"],
                                                      ["Rz","rz"],
                                                    ]), "axis");
          this.setInputsInline(true);
          this.setOutput(true, "Number");
          this.setColour(20);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
        }
      };

      Blockly.Blocks['logic_custom_flag'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type; 
          this.hasBlockNo = false; 
          this.hasBlockFlow = false; 
          this.appendDummyInput()
              .appendField(new Blockly.FieldDropdown(self.flagNames), "name")
          this.setInputsInline(true);
          this.setOutput(true, "Boolean");
          this.setColour(200);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
        }
      };
  
      Blockly.Blocks['wait_timer'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("wait until")
              .appendField(new Blockly.FieldDropdown(self.numberNames), "name")
              .appendField("msec")
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(40);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };
  
      Blockly.Blocks['connect_plc'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              // .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField("connect to")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["maker","maker"],
                                                      ["KEYENCE","keyence"],
                                                    ]), "plc_maker")
              .appendField("with")
              // .appendField(new Blockly.FieldTextInput("octetNo1"), "octet1")
              .appendField(new Blockly.FieldNumber(192), "octet1")
              .appendField(".")
              // .appendField(new Blockly.FieldTextInput("octetNo2"), "octet2")
              .appendField(new Blockly.FieldNumber(168), "octet2")
              .appendField(".")
              // .appendField(new Blockly.FieldTextInput("octetNo3"), "octet3")
              .appendField(new Blockly.FieldNumber(250), "octet3")
              .appendField(".")
              // .appendField(new Blockly.FieldTextInput("octetNo4"), "octet4")
              .appendField(new Blockly.FieldNumber(10), "octet4")
              .appendField(":")
              // .appendField(new Blockly.FieldTextInput("portNo"), "portNo")
              .appendField(new Blockly.FieldNumber(5000), "port")
              
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(230);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        },
      };

      Blockly.Blocks['plc_bit'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = false; 
          this.hasBlockFlow = false; 
          this.appendDummyInput()
              // .appendField("BIT")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["deviceName","device_name"], 
                                                      ["R","R"], 
                                                      ["MR","MR"],
                                                     ]), "device_name")
              .appendField(new Blockly.FieldNumber(0), "device_word_no")
              // .appendField(new Blockly.FieldDropdown([
                                                      // ["deviceWordNo","device_word_no"], 
                                                    // ]), "device_word_no")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["deviceBitNo","device_bit_no"], 
                                                      ["00","00"], 
                                                      ["01","01"],
                                                      ["02","02"],
                                                      ["03","03"],
                                                      ["04","04"],
                                                      ["05","05"],
                                                      ["06","06"],
                                                      ["07","07"],
                                                      ["08","08"],
                                                      ["09","09"],
                                                      ["10","10"],
                                                      ["11","11"],
                                                      ["12","12"],
                                                      ["13","13"],
                                                      ["14","14"],
                                                      ["15","15"],
                                                     ]), "device_bit_no")
              //  .appendField("from")
              //  .appendField(new Blockly.FieldDropdown([ 
              //                                           ["type", "type"],
              //                                           ["KEYENCE","keyence"],
              //                                         ]), "plc_maker");
          this.setInputsInline(true);
          this.setOutput(true, "Boolean");
          this.setColour(230);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };

      Blockly.Blocks['plc_word'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = false; 
          this.hasBlockFlow = false; 
          this.appendDummyInput()
              // .appendField("WORD")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["deviceName","device_name"], 
                                                      ["DM","DM"], 
                                                      // ["EM","EM"],
                                                     ]), "device_name")
              // .appendField(new Blockly.FieldDropdown([
              //                                         ["deviceWordNo","device_word_no"], 
              //                                        ]), "device_word_no")
              .appendField(new Blockly.FieldNumber(0), "device_word_no")
              // .appendField(new Blockly.FieldDropdown([ 
              //                                          ["type", "type"],
              //                                         ["KEYENCE","keyence"],
              //                                       ]), "plc_maker");
          this.setInputsInline(true);
          this.setOutput(true, "Number");
          this.setColour(230);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };

      Blockly.Blocks['set_plc_bit'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField('set')
              .appendField(new Blockly.FieldDropdown([
                                                      // ["deviceName","device_name"], 
                                                      ["R","R"], 
                                                      ["MR","MR"],
                                                     ]), "device_name")
              .appendField(new Blockly.FieldNumber(0), "device_word_no")
              // .appendField(new Blockly.FieldDropdown([
              //                                         ["deviceWordNo","device_word_no"], 
              //                                       ]), "device_word_no")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["deviceBitNo","device_bit_no"], 
                                                      ["00","00"],
                                                      ["01","01"],
                                                      ["02","02"],
                                                      ["03","03"],
                                                      ["04","04"],
                                                      ["05","05"],
                                                      ["06","06"],
                                                      ["07","07"],
                                                      ["08","08"],
                                                      ["09","09"],
                                                      ["10","10"],
                                                      ["11","11"],
                                                      ["12","12"],
                                                      ["13","13"],
                                                      ["14","14"],
                                                      ["15","15"],
                                                     ]), "device_bit_no")
              .appendField('to')
              .appendField(new Blockly.FieldDropdown([
                                                      // ["bitStatus","bitStatus"], 
                                                      ["ON","on"], 
                                                      ["OFF","off"]
                                                    ]), "bit_state")
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(230);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };
  
      Blockly.Blocks['set_plc_bit_during'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField('set')
              .appendField(new Blockly.FieldDropdown([
                                                      // ["deviceName","device_name"], 
                                                      ["R","R"], 
                                                      ["MR","MR"],
                                                     ]), "device_name")
              .appendField(new Blockly.FieldNumber(0), "device_word_no")
              // .appendField(new Blockly.FieldDropdown([
              //                                         ["deviceWordNo","device_word_no"], 
              //                                       ]), "device_word_no")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["deviceBitNo","device_bit_no"], 
                                                      ["00","00"],
                                                      ["01","01"],
                                                      ["02","02"],
                                                      ["03","03"],
                                                      ["04","04"],
                                                      ["05","05"],
                                                      ["06","06"],
                                                      ["07","07"],
                                                      ["08","08"],
                                                      ["09","09"],
                                                      ["10","10"],
                                                      ["11","11"],
                                                      ["12","12"],
                                                      ["13","13"],
                                                      ["14","14"],
                                                      ["15","15"],
                                                     ]), "device_bit_no")
              .appendField('to')
              .appendField(new Blockly.FieldDropdown([
                                                      // ["bitStatus","bitStatus"], 
                                                      ["ON","on"], 
                                                      ["OFF","off"]
                                                    ]), "bit_state")
              .appendField("during")
              .appendField(new Blockly.FieldDropdown(self.numberNames), "number_name")
              .appendField("msec");
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(230);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };

      Blockly.Blocks['set_plc_bit_until'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField('set')
              .appendField(new Blockly.FieldDropdown([
                                                      // ["outDeviceName","outDevice_name"], 
                                                      ["R","R"], 
                                                      ["MR","MR"],
                                                     ]), "output_device_name")
              .appendField(new Blockly.FieldNumber(0), "output_device_word_no")
              // .appendField(new Blockly.FieldDropdown([
                                                      // ["outDeviceWordNo","out_device_word_no"], 
                                                    // ]), "outDevice_word_no")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["outDeviceBitNo","out_device_bit_no"], 
                                                      ["00","00"],
                                                      ["01","01"],
                                                      ["02","02"],
                                                      ["03","03"],
                                                      ["04","04"],
                                                      ["05","05"],
                                                      ["06","06"],
                                                      ["07","07"],
                                                      ["08","08"],
                                                      ["09","09"],
                                                      ["10","10"],
                                                      ["11","11"],
                                                      ["12","12"],
                                                      ["13","13"],
                                                      ["14","14"],
                                                      ["15","15"],
                                                     ]), "output_device_bit_no")
              .appendField('to')
              .appendField(new Blockly.FieldDropdown([
                                                      // ["outBitStatus","out_bit_status"], 
                                                      ["ON","on"], 
                                                      ["OFF","off"]
                                                    ]), "output_bit_state")
              .appendField("until")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["inDeviceName","inDevice_name"], 
                                                      ["R","R"],
                                                      ["MR","MR"],
                                                    ]), "input_device_name")
              .appendField(new Blockly.FieldNumber(0), "input_device_word_no")
              // .appendField(new Blockly.FieldDropdown([
              //                                         ["inDeviceWordNo","inDevice_word_no"], 
              //                                       ]), "in_device_word_no")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["inDeviceBitNo","in_device_bit_no"], 
                                                      ["00","00"],
                                                      ["01","01"],
                                                      ["02","02"],
                                                      ["03","03"],
                                                      ["04","04"],
                                                      ["05","05"],
                                                      ["06","06"],
                                                      ["07","07"],
                                                      ["08","08"],
                                                      ["09","09"],
                                                      ["10","10"],
                                                      ["11","11"],
                                                      ["12","12"],
                                                      ["13","13"],
                                                      ["14","14"],
                                                      ["15","15"],
                                                    ]), "input_device_bit_no")
              .appendField("=")
              .appendField(new Blockly.FieldDropdown([
                                                      // ["inBitStatus","in_bit_status"], 
                                                      ["ON","on"], 
                                                      ["OFF","off"]
                                                    ]), "input_bit_state")
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(230);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };

      // Blockly.Blocks['set_off_plc_bit'] = {
      //   init: function() {
      //     this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
      //     this.customId = this.type + '@' + this.blockNo; 
      //     this.hasBlockNo = true; 
      //     this.hasBlockFlow = true; 
      //     this.appendDummyInput()
      //         .appendField(`(${this.blockNo})`, "blockNoField")
      //         .appendField('set off bit device')
      //         .appendField(new Blockly.FieldDropdown([["R","R"], 
      //                                                 ["MR","MR"],
      //                                                ]), "device_name")
      //         .appendField(new Blockly.FieldNumber(0), "device_word_no")
      //         .appendField(new Blockly.FieldDropdown([["00","00"], 
      //                                                 ["01","01"],
      //                                                 ["02","02"],
      //                                                 ["03","03"],
      //                                                 ["04","04"],
      //                                                 ["05","05"],
      //                                                 ["06","06"],
      //                                                 ["07","07"],
      //                                                 ["08","08"],
      //                                                 ["09","09"],
      //                                                 ["10","10"],
      //                                                 ["11","11"],
      //                                                 ["12","12"],
      //                                                 ["13","13"],
      //                                                 ["14","14"],
      //                                                 ["15","15"],
      //                                                ]), "device_bit_no");
      //     this.setInputsInline(true);
      //     this.setPreviousStatement(true, null);
      //     this.setNextStatement(true, null);
      //     this.setColour(230);
      //     this.setTooltip("");
      //     this.setHelpUrl("");
      //     this.originalColor = this.getColour();
      //   }
      // };

      Blockly.Blocks['set_plc_word'] = {
        init: function() {
          this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
          this.customId = this.type + '@' + this.blockNo; 
          this.hasBlockNo = true; 
          this.hasBlockFlow = true; 
          this.appendDummyInput()
              .appendField(`(${this.blockNo})`, "blockNoField")
              .appendField('set')
              .appendField(new Blockly.FieldNumber(0), "value")
              // .appendField(new Blockly.FieldDropdown([
              //                                         ["value","value"], 
              //                                       ]), "value")
              .appendField('to')
              .appendField(new Blockly.FieldDropdown([
                                                      // ["deviceName","device_name"], 
                                                      ["DM","DM"], 
                                                      // ["EM","EM"],
                                                     ]), "device_name")
              .appendField(new Blockly.FieldNumber(0), "device_word_no")
              // .appendField(new Blockly.FieldDropdown([
              //                                         ["deviceWordNo","device_word_no"], 
              //                                       ]), "device_word_no")
          this.setInputsInline(true);
          this.setPreviousStatement(true, "process");
          this.setNextStatement(true, "process");
          this.setColour(230);
          this.setTooltip("");
          this.setHelpUrl("");
          this.originalColor = this.getColour();
          this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
          self.addTimeoutOption(this);
        }
      };

      // デフォルトブロックにカスタムメンバ変数追加
      Blockly.Blocks['controls_if'] = Blockly.Blocks['controls_if'] || {};
      const controls_if = Blockly.Blocks['controls_if'].init;
      Blockly.Blocks['controls_if'].init = function() {
        // 元の controls_if の init を呼び出す
        controls_if.call(this);
      
        // blockNo のようなカスタムプロパティを追加
        this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
        this.customId = this.type + '@' + this.blockNo; 
        this.hasBlockNo = true; 
        this.hasBlockFlow = true; 
        this.setPreviousStatement(true, "process");
        this.setNextStatement(true, "process");
        this.setColour(200);
        this.originalColor = this.getColour();
        // this.setNextStatement(false);
       
      };
      Blockly.Blocks['logic_compare'] = Blockly.Blocks['logic_compare'] || {};
      const logic_compare = Blockly.Blocks['logic_compare'].init;
      Blockly.Blocks['logic_compare'].init = function() {
        // 元の controls_if の init を呼び出す
        logic_compare.call(this);
      
        // blockNo のようなカスタムプロパティを追加
        this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
        this.customId = this.type; 
        this.hasBlockNo = false; 
        this.hasBlockFlow = false; 
        this.setColour(200);
        this.originalColor = this.getColour();
      };
      Blockly.Blocks['logic_operation'] = Blockly.Blocks['logic_operation'] || {};
      const logic_operation = Blockly.Blocks['logic_operation'].init;
      Blockly.Blocks['logic_operation'].init = function() {
        // 元の controls_if の init を呼び出す
        logic_operation.call(this);
      
        // blockNo のようなカスタムプロパティを追加
        this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
        this.customId = this.type; 
        this.hasBlockNo = false; 
        this.hasBlockFlow = false; 
        this.setColour(200);
        this.originalColor = this.getColour();
      };
      Blockly.Blocks['logic_negate'] = Blockly.Blocks['logic_negate'] || {};
      const logic_negate = Blockly.Blocks['logic_negate'].init;
      Blockly.Blocks['logic_negate'].init = function() {
        // 元の controls_if の init を呼び出す
        logic_negate.call(this);
        // blockNo のようなカスタムプロパティを追加
        this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
        this.customId = this.type; 
        this.hasBlockNo = false; 
        this.hasBlockFlow = false; 
        this.setColour(200);
        this.originalColor = this.getColour();
      };
      Blockly.Blocks['logic_boolean'] = Blockly.Blocks['logic_boolean'] || {};
      const logic_boolean = Blockly.Blocks['logic_boolean'].init;
      Blockly.Blocks['logic_boolean'].init = function() {
        // 元の controls_if の init を呼び出す
        logic_boolean.call(this);
      
        // blockNo のようなカスタムプロパティを追加
        this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
        this.customId = this.type; 
        this.hasBlockNo = false; 
        this.hasBlockFlow = false; 
        this.setColour(200);
        this.originalColor = this.getColour();
      };
      Blockly.Blocks['math_number'] = Blockly.Blocks['math_number'] || {};
      const math_number = Blockly.Blocks['math_number'].init;
      Blockly.Blocks['math_number'].init = function() {
        // 元の controls_if の init を呼び出す
        math_number.call(this);
      
        // blockNo のようなカスタムプロパティを追加
        this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
        this.customId = this.type; 
        this.hasBlockNo = false; 
        this.hasBlockFlow = false; 
        this.setColour(160);
        this.originalColor = this.getColour();
      };
      Blockly.Blocks['math_arithmetic'] = Blockly.Blocks['math_arithmetic'] || {};
      const math_arithmetic = Blockly.Blocks['math_arithmetic'].init;
      Blockly.Blocks['math_arithmetic'].init = function() {
        // 元の controls_if の init を呼び出す
        math_arithmetic.call(this);
      
        // blockNo のようなカスタムプロパティを追加
        this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
        this.customId = this.type; 
        this.hasBlockNo = false; 
        this.hasBlockFlow = false; 
        this.setColour(160);
        this.originalColor = this.getColour();
        // this.appendDummyInput()
        //     .appendField(`(${this.blockNo})`, "blockNoField");
      };
      
      Blockly.Blocks['procedures_defnoreturn'] = Blockly.Blocks['procedures_defnoreturn'] || {};
      const procedures_defnoreturn = Blockly.Blocks['procedures_defnoreturn'].init;
      Blockly.Blocks['procedures_defnoreturn'].init = function() {
        // 元の controls_if の init を呼び出す
        procedures_defnoreturn.call(this);
      
        // blockNo のようなカスタムプロパティを追加
        this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
        this.customId = this.type + '@' + this.blockNo; 
        this.hasBlockNo = true; 
        this.hasBlockFlow = true; 
        this.setColour(290);
        this.originalColor = this.getColour();     

        // コメントボタンを無効にする
        this.setCommentText(null);
        // ミューテーションボタンを無効にする
        this.setMutator(null);
        // this.appendDummyInput()
        //     .appendField(`(${this.blockNo})`, "blockNoField");
      };

      Blockly.Blocks['procedures_callnoreturn'] = Blockly.Blocks['procedures_callnoreturn'] || {};
      const procedures_callnoreturn = Blockly.Blocks['procedures_callnoreturn'].init;
      Blockly.Blocks['procedures_callnoreturn'].init = function() {
        // 元の controls_if の init を呼び出す
        procedures_callnoreturn.call(this);
      
        // blockNo のようなカスタムプロパティを追加
        this.blockNo = self.blockUtilsIns.getBlockCount(this.type); 
        this.customId = this.type + '@' + this.blockNo; 
        this.hasBlockNo = true; 
        this.hasBlockFlow = true; 
        this.setColour(290);
        this.originalColor = this.getColour();
        // this.timeoutMillis = INIT_TIMEOUT_MILLIS;                                                  
        // self.addTimeoutOption(this);
    };

      // `procedures_defreturn` を無効化
      Blockly.Blocks['procedures_defreturn'] = null;

      // `procedures_ifreturn` を無効化
      Blockly.Blocks['procedures_ifreturn'] = null;

    }
}

class BlockCode {
  constructor(blockUtilsIns) {
    this.blockUtilsIns = blockUtilsIns;
    // this.blockFormIns = blockFormIns;
    this.addr_str = 'MR';
    this.buttonLampDevice = 'R';
    this.buttonReadyAddr = 0;
    this.lampReadyAddr = 5000;
    this.buttonRunAddr = 2;
    this.lampRunAddr = 5002;
    this.buttonPauseAddr = 3;
    this.lampPauseAddr = 5003;
    this.userErrorNo = 801;
    // this.userErrorNo = 1501;
  }

  getBlockAddr(blockId) {
    const block_pos = this.blockUtilsIns.getBlockPositionCustom(blockId, this.blockUtilsIns.all_block_flow);
    const block_flow = this.blockUtilsIns.all_block_flow[block_pos.thread_no][block_pos.flow_no];
  
    return {
      index: block_flow.index,
      prev_index: block_flow.prevIndex,
      prev_branch_num: block_flow.prevBranchNum,
      survival1_addr_list: block_flow.survival1,
      reset_addr_list: block_flow.reset,
      onset_addr: block_flow.onset,
      start_addr: block_flow.start,
      def_func_start_addr: block_flow.defFuncStart,
      stop1_addr: block_flow.stop1,
      stop2_addr: block_flow.stop2,
      stop3_addr: block_flow.stop3,
      stop4_addr: block_flow.stop4,
      stop5_addr: block_flow.stop5,
      stop6_addr: block_flow.stop6,
      stop7_addr: block_flow.stop7,
      stop8_addr: block_flow.stop8,
      stop9_addr: block_flow.stop9,
      stop10_addr: block_flow.stop10,
    };
  }

  defineBlockCode() {
    const self = this; // thisの値を安定化させる

    python.pythonGenerator.forBlock['select_robot'] = function(block, generator) {
      //////////////////////////////////////////////////
      // アドレス参照
      //////////////////////////////////////////////////   
      const myBlock = self.getBlockAddr(block.customId); 
      //////////////////////////////////////////////////
      // 前処理
      //////////////////////////////////////////////////
      // const robot_name = block.getFieldValue('robot_name_list');

      //////////////////////////////////////////////////
      // プロセス
      //////////////////////////////////////////////////
      let LF = '\n';
      let INDENT = '  ';
      let line_str = [];
      line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
        else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
      }
      if(myBlock.reset_addr_list){
        for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + `L.ANB(${self.addr_str}, ${myBlock.myBlock.reset_addr_list[i]})` + LF);
      }
      // line_str.push(INDENT + INDENT + INDENT + `L.ANB(R, 5)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(RAC.connected)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(RAC.connected)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);

      //////////////////////////////////////////////////
      // プロセス後動作
      //////////////////////////////////////////////////
      line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
      // timeout
      if (Number(block.timeoutMillis) !== -1){
        line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);  
      }
      // action
      line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
      // line_str.push(INDENT + INDENT + INDENT +`L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      // line_str.push(INDENT + INDENT + INDENT +`if (L.aax & L.iix):` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "RAC.send_command('getRobotStatus()')" + LF);  
      line_str.push(INDENT + INDENT + INDENT +`if(RAC.connected):` + LF);
      // ロボット状態取得
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "input_port = RB.getInput()" + LF);  
      line_str.push(INDENT + INDENT + INDENT + INDENT + "RAC.send_command('getRobotStatus()')" + LF);  
      line_str.push(INDENT + INDENT + INDENT + INDENT + "RAC.send_command('updateRedis()')" + LF);  
      line_str.push(INDENT + INDENT + INDENT + INDENT + "robot_status = RAC.get_status()" + LF);  
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "servo = robot_status['servo']" + LF);  
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "origin = robot_status['origin']" + LF);  
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "arrived = robot_status['arrived']" + LF); 
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "error = robot_status['error']" + LF); 
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "error_id = robot_status['error_id']" + LF); 
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "input_signal = robot_status['input_signal']" + LF); 
      line_str.push(INDENT + INDENT + INDENT + INDENT + "drive.handle_auto_sidebar(robot_status, number_param_yaml, flag_param_yaml)" + LF);
      // リセット
      line_str.push(INDENT + INDENT + INDENT + INDENT + "L.LD(MR, 307)" + LF);  
      line_str.push(INDENT + INDENT + INDENT + INDENT + "if (L.aax & L.iix):" + LF);  
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + "RAC.send_command('resetError()')" + LF);  
      // 一時停止
      line_str.push(INDENT + INDENT + INDENT + INDENT + "L.LD(MR, 304)" + LF); 
      line_str.push(INDENT + INDENT + INDENT + INDENT + "if (L.aax & L.iix):" + LF); 
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + "RAC.send_command('stopRobot()')" + LF); 
      // システムステータス
      line_str.push(INDENT + INDENT + INDENT + INDENT + "flag_param_yaml['F480']['value'] = L.getRelay(MR, 300)" + LF); 
      line_str.push(INDENT + INDENT + INDENT + INDENT + "flag_param_yaml['F481']['value'] = L.getRelay(MR, 302)" + LF); 
      line_str.push(INDENT + INDENT + INDENT + INDENT + "flag_param_yaml['F482']['value'] = L.getRelay(MR, 304)" + LF); 
      line_str.push(INDENT + INDENT + INDENT + INDENT + "flag_param_yaml['F483']['value'] = L.getRelay(MR, 501)" + LF); 
      line_str.push(INDENT + INDENT + INDENT + INDENT + "flag_param_yaml['F484']['value'] = L.getRelay(MR, 307)" + LF); 

      // パトライト
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])" + LF); 
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "L.ANB(MR, 501)" + LF); 
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "L.OUT(L.local_R['patlite_status[0]']['name'], L.local_R['patlite_status[0]']['addr'])" + LF); 
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "patlite_status['green'] = L.getRelay(L.local_R['patlite_status[0]']['name'], L.local_R['patlite_status[0]']['addr'])" + LF); 
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "L.LD(MR, 501)" + LF); 
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "L.OUT(L.local_R['patlite_status[1]']['name'], L.local_R['patlite_status[1]']['addr'])" + LF); 
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "patlite_status['red'] = L.getRelay(L.local_R['patlite_status[1]']['name'], L.local_R['patlite_status[1]']['addr'])" + LF); 
      // ロボットステータス
      line_str.push(INDENT + INDENT + INDENT + INDENT + "if robot_status['current_pos']:" + LF);  
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + "current_pos['x'] = robot_status['current_pos'][0]" + LF);  
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + "current_pos['y'] = robot_status['current_pos'][1]" + LF);  
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + "current_pos['z'] = robot_status['current_pos'][2]" + LF);  
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + "current_pos['rx'] = robot_status['current_pos'][3]" + LF);  
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + "current_pos['ry'] = robot_status['current_pos'][4]" + LF);  
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + "current_pos['rz'] = robot_status['current_pos'][5]" + LF);  
      line_str.push(INDENT + INDENT + INDENT +`else:` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + "RAC.send_command('getRobotStatus()')" + LF);  
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "servo = False" + LF); 
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "origin = False" + LF); 
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "arrived = False" + LF); 
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "error = False" + LF); 
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "error_id = 0" + LF); 
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "if (robot_status['error_id'] == 0): drive.raise_error(no=10, error_yaml=error_yaml)" + LF); 
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "servo = False" + LF); 
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "origin = False" + LF); 
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "arrived = False" + LF); 
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "error = True" + LF); 
      // line_str.push(INDENT + INDENT + INDENT + INDENT + "error_id = 10" + LF); 
      line_str.push(INDENT + INDENT + LF);      

      return line_str.join("");
    };
      
    python.pythonGenerator.forBlock['connect_camera'] = function(block, generator) {
      //////////////////////////////////////////////////
      // アドレス参照
      //////////////////////////////////////////////////   
      const myBlock = self.getBlockAddr(block.customId); 

      //////////////////////////////////////////////////
      // 前処理
      //////////////////////////////////////////////////
      const camera_no = block.getFieldValue('camera_list');
      const octet1 = block.getFieldValue('octet1');
      const octet2 = block.getFieldValue('octet2');
      const octet3 = block.getFieldValue('octet3');
      const octet4 = block.getFieldValue('octet4');
      const port = block.getFieldValue('port');

      //////////////////////////////////////////////////
      // プロセス
      //////////////////////////////////////////////////
      let LF = '\n';
      let INDENT = '  ';
      let line_str = [];
      line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
        else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
      }
      if(myBlock.reset_addr_list){
        for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + `L.ANB(${self.addr_str}, ${myBlock.myBlock.reset_addr_list[i]})` + LF);
      }
      if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.AND(camera_connected[${camera_no}-1])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);

      //////////////////////////////////////////////////
      // プロセス後動作
      //////////////////////////////////////////////////
      line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
      // timeout
      if (Number(block.timeoutMillis) !== -1){
        line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);  
      }
      // action
      line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
      // Prev.ボタン対応
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] !== 992002){
          if (i === 0){
            line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
            line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
          }
          else{
            line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
          }
          line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
        }
      }
      line_str.push(INDENT + INDENT + INDENT +`L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT +`if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `camera_instance[${camera_no}-1] = TCPClient('${octet1}.${octet2}.${octet3}.${octet4}',${port})` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `if camera_instance[${camera_no}-1].connect():` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `camera_connected[${camera_no}-1] = True` + LF);
      // error
      line_str.push(INDENT + INDENT + INDENT + `#;error:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `if (camera_connected[${camera_no}-1] == False):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}+0, message=f"${block.customId}:Connection is failed.", error_yaml=error_yaml)` + LF);  
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}+0, error_yaml=error_yaml)` + LF); 
      line_str.push(LF);      

      return line_str.join("");
    };

    python.pythonGenerator.forBlock['run_camera_wait'] = function(block, generator) {
      //////////////////////////////////////////////////
      // アドレス参照
      //////////////////////////////////////////////////   
      const myBlock = self.getBlockAddr(block.customId); 
      //////////////////////////////////////////////////
      // 前処理
      //////////////////////////////////////////////////
      const camera_no = block.getFieldValue('camera_list');
      const program_no = block.getFieldValue('program_list');
      //////////////////////////////////////////////////
      // プロセス
      //////////////////////////////////////////////////
      let LF = '\n';
      let INDENT = '  ';
      let line_str = [];
      line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
        else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
      }
      if(myBlock.reset_addr_list){
        for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + `L.ANB(${self.addr_str}, ${myBlock.myBlock.reset_addr_list[i]})` + LF);
      }
      if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.AND(camera_responded[${camera_no}-1])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      //////////////////////////////////////////////////
      // プロセス後動作
      //////////////////////////////////////////////////
      line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
      if (Number(block.timeoutMillis) !== -1){
        line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);  
      }
      line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
      // Prev.ボタン対応
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] !== 992002){
          if (i === 0){
            line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
            line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
          }
          else{
            line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
          }
          line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
        }
      }
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `camera_responded[${camera_no}-1] = False` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `flag_param_yaml['F' + str(490 + ${camera_no}-1)]['value'] = False` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `camera_instance[${camera_no}-1].send_message('TR1,${program_no},0,0,0\\r\\n')` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `response = camera_instance[${camera_no}-1].receive_message()` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `if response:` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `print(f"Received: {response}")` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `splitted_response = []` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `for index, element in enumerate(response.split(',')):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + INDENT + `if '\\r\\n' in element:` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + INDENT + INDENT + `splitted_response.append(element.strip())` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + INDENT + INDENT + `break` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + INDENT + `splitted_response.append(element)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `camera_responded[${camera_no}-1] = True` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `flag_param_yaml['F' + str(490 + ${camera_no}-1)]['value'] = True` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `camera_results[${camera_no}-1]['test'] = float(splitted_response[0])` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `camera_results[${camera_no}-1]['x'] = float(splitted_response[1])` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `camera_results[${camera_no}-1]['y'] = float(splitted_response[2])` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `camera_results[${camera_no}-1]['r'] = float(splitted_response[4])` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `camera_results[${camera_no}-1]['text'] = splitted_response[5]` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `number_param_yaml['N' + str(470 + ${camera_no}-1)]['value'] = camera_results[${camera_no}-1]['test'] ` + LF);
      line_str.push(LF);              

      return line_str.join("");
    };

    python.pythonGenerator.forBlock['run_camera'] = function(block, generator) {
      //////////////////////////////////////////////////
      // アドレス参照
      //////////////////////////////////////////////////   
      const myBlock = self.getBlockAddr(block.customId); 

      //////////////////////////////////////////////////
      // 前処理
      //////////////////////////////////////////////////
      const camera_no = block.getFieldValue('camera_list');
      const program_no = block.getFieldValue('program_list');
      //////////////////////////////////////////////////
      // プロセス
      //////////////////////////////////////////////////
      let LF = '\n';
      let INDENT = '  ';
      let line_str = [];
      line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
        else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
      }
      if(myBlock.reset_addr_list){
        for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + `L.ANB(${self.addr_str}, ${myBlock.myBlock.reset_addr_list[i]})` + LF);
      }
      if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      //////////////////////////////////////////////////
      // プロセス後動作
      //////////////////////////////////////////////////
      line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
      // timeout
      if (Number(block.timeoutMillis) !== -1){
        line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);  
      }
      line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
      // Prev.ボタン対応
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] !== 992002){
          if (i === 0){
            line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
            line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
          }
          else{
            line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
          }
          line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
        }
      }
      line_str.push(INDENT + INDENT + INDENT +`L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT +`if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `camera_responded[${camera_no}-1] = False` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `camera_instance[${camera_no}-1].send_message('TR1,${program_no},0,0,0\\r\\n')` + LF);
      line_str.push(LF);              

      return line_str.join("");
    };

    python.pythonGenerator.forBlock['wait_camera'] = function(block, generator) {
      //////////////////////////////////////////////////
      // アドレス参照
      //////////////////////////////////////////////////   
      const myBlock = self.getBlockAddr(block.customId); 
      //////////////////////////////////////////////////
      // 前処理
      //////////////////////////////////////////////////
      const camera_no = block.getFieldValue('camera_list');
      //////////////////////////////////////////////////
      // プロセス
      //////////////////////////////////////////////////
      let LF = '\n';
      let INDENT = '  ';
      let line_str = [];
      line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
        else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
      }
      if(myBlock.reset_addr_list){
        for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + `L.ANB(${self.addr_str}, ${myBlock.myBlock.reset_addr_list[i]})` + LF);
      }
      if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.AND(camera_responded[${camera_no}-1])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      //////////////////////////////////////////////////
      // プロセス後動作
      //////////////////////////////////////////////////
      line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
      // timeout
      if (Number(block.timeoutMillis) !== -1){
        line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);  
      }
      line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
      // Prev.ボタン対応
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] !== 992002){
          if (i === 0){
            line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
            line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
          }
          else{
            line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
          }
          line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
        }
      }
      line_str.push(INDENT + INDENT + INDENT +`L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT +`if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `response = camera_instance[${camera_no}-1].receive_message()` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `if response:` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `print(f"Received: {response}")` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `splitted_response = []` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `for index, element in enumerate(response.split(',')):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + INDENT + `if '\\r\\n' in element:` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + INDENT + INDENT + `splitted_response.append(element.strip())` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + INDENT + INDENT + `break` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + INDENT + `splitted_response.append(element)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `camera_responded[${camera_no}-1] = True` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `camera_results[${camera_no}-1]['test'] = float(splitted_response[0])` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `camera_results[${camera_no}-1]['x'] = float(splitted_response[1])` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `camera_results[${camera_no}-1]['y'] = float(splitted_response[2])` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `camera_results[${camera_no}-1]['r'] = float(splitted_response[4])` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `camera_results[${camera_no}-1]['text'] = splitted_response[5]` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `number_param_yaml['N' + str(470 + ${camera_no}-1)]['value'] = camera_results[${camera_no}-1]['test'] ` + LF);
      line_str.push(LF);              

      return line_str.join("");
    };

    python.pythonGenerator.forBlock['start_thread'] = function(block, generator) {
      //////////////////////////////////////////////////
      // アドレス参照
      //////////////////////////////////////////////////    
      const myBlock = self.getBlockAddr(block.customId); 
      //////////////////////////////////////////////////
      // 前処理
      //////////////////////////////////////////////////
      const condition = generator.valueToCode(block, 'condition', generator.ORDER_ATOMIC) || '0';
      // 正規表現で or または and で分割する
      // 括弧を削除
      const cleanedInput = condition.replace(/^\(|\)$/g, '');
      // 正規表現で内容とキーワードを抽出
      const matches = [...cleanedInput.matchAll(/(.+?)\s+(or|and)\s+|(.+)$/g)];
      // 分離する配列
      const logic_bits = [];
      // const operators = [];
      // マッチした内容を処理
      matches.forEach(match => {
        if (match[1]) {
          logic_bits.push(match[1].trim());
          // operators.push(match[2].trim());
        } else if (match[3]) {
          logic_bits.push(match[3].trim());
        }
      });
      // // OR ANDブロック用のニーモニック生成
      // operators.forEach((operator, index) => {
      //   if(operator === 'or'){
      //     console.log(`OR ${logic_bits[index]}`);
      //     // 最後の要素なら
      //     if (index === operators.length - 1) {
      //       console.log(`OR ${logic_bits[index+1]}`);
      //     }
      //   }
      //   else if(operator === 'and'){
      //     console.log(`LD ${logic_bits[index]}`);
      //     console.log(`AND ${logic_bits[index+1]}`);
      //     console.log(`ORL`);
      //   }
      //   else{
      //     console.log('operator is wrong.');
      //   }
      // });

      //////////////////////////////////////////////////
      // プロセス
      //////////////////////////////////////////////////
      let LF = '\n';
      let INDENT = '  ';
      let line_str = [];
      line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] === 992002){
          line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
          // line_str.push(INDENT + INDENT + INDENT + `L.ANB(R, 5)` + LF);
          // or 条件
          logic_bits.forEach((logic_bit) => {
            // ブール値なら
            if ((logic_bit === 'True') || (logic_bit === 'False')){
              line_str.push(INDENT + INDENT + INDENT + `L.ANPB('${logic_bit}')` + LF);
            }
            else{
              line_str.push(INDENT + INDENT + INDENT + `L.ANPB(${logic_bit})` + LF);
            }
          });
        }
        else line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
      }
      // line_str.push(INDENT + INDENT + INDENT + `L.LD(${condition})` + LF);
      // line_str.push(INDENT + INDENT + INDENT + `L.ANB(R, 5)` + LF);
      if(myBlock.reset_addr_list){
        for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
      }
      line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      // line_str.push(INDENT + INDENT + INDENT + `L.LDPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      // line_str.push(INDENT + INDENT + INDENT + `L.LD(${condition})` + LF);
      // orの開始条件追加
      // logic_bits.forEach((logic_bit, index) => {
      //   // ブール値なら
      //   if ((logic_bit === 'True') || (logic_bit === 'False')){
      //     if (index === 0) line_str.push(INDENT + INDENT + INDENT + `L.LD('${logic_bit}')` + LF);
      //     else line_str.push(INDENT + INDENT + INDENT + `L.OR('${logic_bit}')` + LF); 
      //   }
      //   else{
      //     if (index === 0) line_str.push(INDENT + INDENT + INDENT + `L.LD(${logic_bit})` + LF);
      //     else line_str.push(INDENT + INDENT + INDENT + `L.OR(${logic_bit})` + LF);  
      //   }
      // });
      // line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + LF);   
      let code = line_str.join("");
      // let branches = ['DO'].map(label => generator.statementToCode(block, label)).join('\n');

      // DOステートメント以降のブロックコードを取得
      var statements_do = python.pythonGenerator.statementToCode(block, 'DO');  
      // 各行の先頭のインデントを削除
      statements_do = statements_do.replace(/^ {2}/gm, '');   

      return code + statements_do;
      };

      python.pythonGenerator.forBlock['create_event'] = function(block, generator) {
        //////////////////////////////////////////////////
        // アドレス参照
        //////////////////////////////////////////////////    
        const myBlock = self.getBlockAddr(block.customId); 
  
        //////////////////////////////////////////////////
        // プロセス
        //////////////////////////////////////////////////
        let LF = '\n';
        let INDENT = '  ';
        let line_str = [];
        line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LDPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   
        line_str.push(INDENT + INDENT + INDENT + LF);   
        let code = line_str.join("");
        // let branches = ['DO'].map(label => generator.statementToCode(block, label)).join('\n');
  
        // DOステートメント以降のブロックコードを取得
        var statements_do = python.pythonGenerator.statementToCode(block, 'EVENT');  
        // 各行の先頭のインデントを削除
        statements_do = statements_do.replace(/^ {2}/gm, '');   
  
        return code + statements_do;
        };

    python.pythonGenerator.forBlock['moveL'] = function(block, generator) {  
      //////////////////////////////////////////////////
      // 前処理
      //////////////////////////////////////////////////
      const point_name = block.getFieldValue('point_name_list');
      const controlX = block.getFieldValue('control_x');
      const controlY = block.getFieldValue('control_y');
      const controlZ = block.getFieldValue('control_z');
      const controlRx = block.getFieldValue('control_rx');
      const controlRy = block.getFieldValue('control_ry');
      const controlRz = block.getFieldValue('control_rz');
      const pallet_no = block.getFieldValue('pallet_list');
      const camera_no = block.getFieldValue('camera_list');
      let point_name_str = String(point_name);
      let x = controlX === "enable" ? self.blockUtilsIns.teachingJson[point_name_str]['x_pos'] : "current_pos['x']";
      let y = controlY === "enable" ? self.blockUtilsIns.teachingJson[point_name_str]['y_pos'] : "current_pos['y']";
      let z = controlZ === "enable" ? self.blockUtilsIns.teachingJson[point_name_str]['z_pos'] : "current_pos['z']";
      let rx = controlRx === "enable" ? self.blockUtilsIns.teachingJson[point_name_str]['rx_pos'] : "current_pos['rx']";
      let ry = controlRy === "enable" ? self.blockUtilsIns.teachingJson[point_name_str]['ry_pos'] : "current_pos['ry']";
      let rz = controlRz === "enable" ? self.blockUtilsIns.teachingJson[point_name_str]['rz_pos'] : "current_pos['rz']";
      let vel = self.blockUtilsIns.teachingJson[point_name_str]['vel'];
      let acc = self.blockUtilsIns.teachingJson[point_name_str]['acc'];
      let dec = self.blockUtilsIns.teachingJson[point_name_str]['dec'];
      let dist = self.blockUtilsIns.teachingJson[point_name_str]['dist'];
      let stime = self.blockUtilsIns.teachingJson[point_name_str]['stime'];
      let tool = self.blockUtilsIns.teachingJson[point_name_str]['tool'];
      let global_override = self.blockUtilsIns.override;
    
      //////////////////////////////////////////////////
      // アドレス参照
      //////////////////////////////////////////////////    
      const myBlock = self.getBlockAddr(block.customId); 

      //////////////////////////////////////////////////
      // プロセス
      //////////////////////////////////////////////////
      let LF = '\n';
      let line_str = [];
      let INDENT = '  ';
      line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
        else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
      }
      if(myBlock.reset_addr_list){
        for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
      }
      if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.AND(robot_status['arrived'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_T['move_static_timer[${myBlock.index}]']['name'], L.local_T['move_static_timer[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);

      //////////////////////////////////////////////////
      // プロセス後動作
      //////////////////////////////////////////////////
      line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
      // timeout
      if (Number(block.timeoutMillis) !== -1){
        line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `if ((L.aax & L.iix) and (RAC.connected)):` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
      }
        // error
      line_str.push(INDENT + INDENT + INDENT + `#;error:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if ((L.aax & L.iix) and (RAC.connected)):` + LF);
      // ロボットAPI固有エラー
      line_str.push(INDENT + INDENT + INDENT + INDENT + `if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)` + LF); 
      // ロボットAPI共通エラー
      line_str.push(INDENT + INDENT + INDENT + INDENT + `if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message=f"${block.customId}:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)` + LF);  
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)` + LF); 
      // パラメータ設定エラー
      line_str.push(INDENT + INDENT + INDENT + INDENT + `if ((${vel} == 0) or (${acc} == 0) or (${dec} == 0)):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)` + LF); 
      // サーボOFFエラー
      line_str.push(INDENT + INDENT + INDENT + INDENT + `if (robot_status['servo'] == False):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:Servo is off.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)` + LF); 
      // // パレットアクセス不可エラー
      // if(Number(pallet_no) > 0) {
      //   line_str.push(INDENT + INDENT + INDENT + INDENT + `if (pallet_settings[${pallet_no}-1]['dst_pocket'] == (pallet_settings[${pallet_no}-1]['row']*pallet_settings[${pallet_no}-1]['col'])+1):` + LF);
      //   line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}+4, message="${block.customId}:Can't move next the numbers in pallet No.${pallet_no}.", error_yaml=error_yaml)` + LF);
      //   line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}+4, error_yaml=error_yaml)` + LF);  
      //   line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)` + LF); 
      // }
      // action
      line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
      // Prev.ボタン対応
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] !== 992002){
          if (i === 0){
            line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
            line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
          }
          else{
            line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
          }
          line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
        }
      }
      // Move命令送信
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(MR, 501)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if ((L.aax & L.iix) and (RAC.connected)):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_x = 0` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_y = 0` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_z = 0` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_rx = 0` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_ry = 0` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_rz = 0` + LF);
      if(Number(pallet_no) > 0) {
        line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_x = offset_x + pallet_offset[${pallet_no}-1]['x']` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_y = offset_y + pallet_offset[${pallet_no}-1]['y']` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_z = offset_z + pallet_offset[${pallet_no}-1]['z']` + LF);
      }
      if(Number(camera_no) > 0) {
        line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_x = offset_x + camera_results[${camera_no}-1]['x']` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_y = offset_y + camera_results[${camera_no}-1]['y']` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_rz = offset_rz + camera_results[${camera_no}-1]['r']` + LF);
      }
      line_str.push(INDENT + INDENT + INDENT + INDENT + `x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(${x}, ${y}, ${z}, ${rx}, ${ry}, ${rz}, ${vel}, ${acc}, ${dec}, ${dist}, ${stime}, ${tool}, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, ${global_override}, program_override)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `RAC.send_command(f'moveAbsoluteLine({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')` + LF);
      // Move命令完了待機
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if ((L.aax & L.iix) and (RAC.connected)):` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_x = 0` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_y = 0` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_z = 0` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_rx = 0` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_ry = 0` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_rz = 0` + LF);
      // if(Number(pallet_no) > 0) {
      //   line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_x = offset_x + pallet_offset[${pallet_no}-1]['x']` + LF);
      //   line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_y = offset_y + pallet_offset[${pallet_no}-1]['y']` + LF);
      //   line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_z = offset_z + pallet_offset[${pallet_no}-1]['z']` + LF);
      // }
      // if(Number(camera_no) > 0) {
      //   line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_x = offset_x + camera_results[${camera_no}-1]['x']` + LF);
      //   line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_y = offset_y + camera_results[${camera_no}-1]['y']` + LF);
      //   line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_rz = offset_rz + camera_results[${camera_no}-1]['r']` + LF);
      // }
      line_str.push(INDENT + INDENT + INDENT + INDENT + `RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')` + LF);
      // 静定時間待機
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.AND(robot_status['arrived'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['move_static_timer[${myBlock.index}]']['addr'], ${stime})` + LF);
      line_str.push(INDENT + INDENT + LF);
      return line_str.join("");
      };

      python.pythonGenerator.forBlock['moveP'] = function(block, generator) {  
        //////////////////////////////////////////////////
        // 前処理
        //////////////////////////////////////////////////
        const point_name = block.getFieldValue('point_name_list');
        const controlX = block.getFieldValue('control_x');
        const controlY = block.getFieldValue('control_y');
        const controlZ = block.getFieldValue('control_z');
        const controlRx = block.getFieldValue('control_rx');
        const controlRy = block.getFieldValue('control_ry');
        const controlRz = block.getFieldValue('control_rz');
        const pallet_no = block.getFieldValue('pallet_list');
        const camera_no = block.getFieldValue('camera_list');
        let point_name_str = String(point_name);
        let x = controlX === "enable" ? self.blockUtilsIns.teachingJson[point_name_str]['x_pos'] : "current_pos['x']";
        let y = controlY === "enable" ? self.blockUtilsIns.teachingJson[point_name_str]['y_pos'] : "current_pos['y']";
        let z = controlZ === "enable" ? self.blockUtilsIns.teachingJson[point_name_str]['z_pos'] : "current_pos['z']";
        let rx = controlRx === "enable" ? self.blockUtilsIns.teachingJson[point_name_str]['rx_pos'] : "current_pos['rx']";
        let ry = controlRy === "enable" ? self.blockUtilsIns.teachingJson[point_name_str]['ry_pos'] : "current_pos['ry']";
        let rz = controlRz === "enable" ? self.blockUtilsIns.teachingJson[point_name_str]['rz_pos'] : "current_pos['rz']";
        let vel = self.blockUtilsIns.teachingJson[point_name_str]['vel'];
        let acc = self.blockUtilsIns.teachingJson[point_name_str]['acc'];
        let dec = self.blockUtilsIns.teachingJson[point_name_str]['dec'];
        let dist = self.blockUtilsIns.teachingJson[point_name_str]['dist'];
        let stime = self.blockUtilsIns.teachingJson[point_name_str]['stime'];
        let tool = self.blockUtilsIns.teachingJson[point_name_str]['tool'];
        let global_override = self.blockUtilsIns.override;
      
        //////////////////////////////////////////////////
        // アドレス参照
        //////////////////////////////////////////////////    
        const myBlock = self.getBlockAddr(block.customId); 

  
        //////////////////////////////////////////////////
        // プロセス
        //////////////////////////////////////////////////
        let LF = '\n';
        let line_str = [];
        let INDENT = '  ';
        line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
        for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
          if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
          else                                          line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        if(myBlock.reset_addr_list){
          for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
        }
        if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
        line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.AND(robot_status['arrived'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_T['move_static_timer[${myBlock.index}]']['name'], L.local_T['move_static_timer[${myBlock.index}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
        line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
        line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
        line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
  
        //////////////////////////////////////////////////
        // プロセス後動作
        //////////////////////////////////////////////////
        line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
        // timeout
        if (Number(block.timeoutMillis) !== -1){
          line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
          line_str.push(INDENT + INDENT + INDENT + `if ((L.aax & L.iix) and (RAC.connected)):` + LF);
          line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
          line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
        }
        // error
        line_str.push(INDENT + INDENT + INDENT + `#;error:` + block.customId + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `if ((L.aax & L.iix) and (RAC.connected)):` + LF);
        // ロボットAPI固有エラー
        line_str.push(INDENT + INDENT + INDENT + INDENT + `if ((robot_status['error'] == True) and ((robot_status['error_id'] > 0) and (robot_status['error_id'] <= 700))):` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=robot_status['error_id'], error_yaml=error_yaml)` + LF); 
        line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)` + LF); 
        // ロボットAPI共通エラー
        line_str.push(INDENT + INDENT + INDENT + INDENT + `if ((robot_status['error'] == True) and ((robot_status['error_id'] > 700) and (robot_status['error_id'] <= 800))):` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message=f"${block.customId}:Robot API error occurred: No.{robot_status['error_id']}", error_yaml=error_yaml)` + LF);  
        line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF); 
        line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)` + LF); 
        // パラメータ設定エラー
        line_str.push(INDENT + INDENT + INDENT + INDENT + `if ((${vel} == 0) or (${acc} == 0) or (${dec} == 0)):` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:Target velocity, acceleration or decelerationis zero.', error_yaml=error_yaml)` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)` + LF); 
        // サーボOFFエラー
        line_str.push(INDENT + INDENT + INDENT + INDENT + `if (robot_status['servo'] == False):` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:Servo is off.', error_yaml=error_yaml)` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)` + LF); 
      //   // パレットアクセス不可エラー
      //   if(Number(pallet_no) > 0) {
      //     line_str.push(INDENT + INDENT + INDENT + INDENT + `if (pallet_settings[${pallet_no}-1]['dst_pocket'] == (pallet_settings[${pallet_no}-1]['row']*pallet_settings[${pallet_no}-1]['col'])+1):` + LF);
      //     line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}+4, message="${block.customId}:Can't move next the numbers in pallet No.${pallet_no}.", error_yaml=error_yaml)` + LF);
      //     line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}+4, error_yaml=error_yaml)` + LF);  
      //     line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.update_auto_status(number_param_yaml, initial_number_param_yaml, error_yaml)` + LF); 
      //   }
        // action
        line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
        // Prev.ボタン対応
        for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
          if(myBlock.survival1_addr_list[i] !== 992002){
            if (i === 0){
              line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
              line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
            }
            else{
              line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
            }
            line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
          }
        }
        // Move命令送信
        line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.ANB(MR, 501)` + LF);
        line_str.push(INDENT + INDENT + INDENT + `if ((L.aax & L.iix) and (RAC.connected)):` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_x = 0` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_y = 0` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_z = 0` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_rx = 0` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_ry = 0` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_rz = 0` + LF);
        if(Number(pallet_no) > 0) {
          line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_x = offset_x + pallet_offset[${pallet_no}-1]['x']` + LF);
          line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_y = offset_y + pallet_offset[${pallet_no}-1]['y']` + LF);
          line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_z = offset_z + pallet_offset[${pallet_no}-1]['z']` + LF);
        }
        if(Number(camera_no) > 0) {
          line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_x = offset_x + camera_results[${camera_no}-1]['x']` + LF);
          line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_y = offset_y + camera_results[${camera_no}-1]['y']` + LF);
          line_str.push(INDENT + INDENT + INDENT + INDENT + `offset_rz = offset_rz + camera_results[${camera_no}-1]['r']` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + INDENT + `x, y, z, rx, ry, rz, vel, acc, dec, dist, stime, tool = L.FB_setRobotParam(${x}, ${y}, ${z}, ${rx}, ${ry}, ${rz}, ${vel}, ${acc}, ${dec}, ${dist}, ${stime}, ${tool}, offset_x, offset_y, offset_z, offset_rx, offset_ry, offset_rz, ${global_override}, program_override)` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `RAC.send_command(f'moveAbsolutePtp({x}, {y}, {z}, {rx}, {ry}, {rz}, {vel}, {acc}, {dec}, {int(tool)})')` + LF);        // Move命令完了待機
        // Move命令完了待機
        line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `if ((L.aax & L.iix) and (RAC.connected)):` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `RAC.send_command(f'waitArrive([{x}, {y}, {z}, {rx}, {ry}, {rz}], {dist})')` + LF);
        // 静定時間待機
        line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.AND(robot_status['arrived'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['move_static_timer[${myBlock.index}]']['addr'], ${stime})` + LF);
        line_str.push(INDENT + INDENT + LF);
  
        return line_str.join("");
        };
  

    python.pythonGenerator.forBlock['return'] = function(block, generator) {
      //////////////////////////////////////////////////
      // アドレス参照
      //////////////////////////////////////////////////    
      const myBlock = self.getBlockAddr(block.customId); 

      //////////////////////////////////////////////////
      // プロセス
      //////////////////////////////////////////////////
      let LF = '\n';
      let INDENT = '  ';
      let line_str = [];
      line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
        else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
      }
      if(myBlock.reset_addr_list){
        for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
      }
      //////////////////////////////////////////////////
      // プロセス
      //////////////////////////////////////////////////
      if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      //////////////////////////////////////////////////
      // プロセス後動作
      //////////////////////////////////////////////////
      line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
      // action
      line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
      // Prev.ボタン対応
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] !== 992002){
          if (i === 0){
            line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
            line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
          }
          else{
            line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
          }
          line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
        }
      }
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `elapsed_time = int((time.perf_counter() - start_time) * 1000)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `L.EM_relay[2020:2020+len(helper.int32_to_uint16s(elapsed_time))] = helper.int32_to_uint16s(elapsed_time)` + LF);    
      line_str.push(INDENT + INDENT + LF);      

      return line_str.join("");
    };


  //   python.pythonGenerator.forBlock['controls_whileUntil'] = function(block, generator) {
  //     //////////////////////////////////////////////////
  //     // アドレス参照
  //     //////////////////////////////////////////////////    
  //     const myBlock = self.getBlockAddr(block.customId);       
  //     //////////////////////////////////////////////////
  //     // シーケンス作成
  //     //////////////////////////////////////////////////
  //     let LF = '\n';
  //     let INDENT = '  ';
  //     let line_str = [];

  //     for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
  //       if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
  //       else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
  //     }
  //     if(myBlock.reset_addr_list){
  //       for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
  //     }
  //     line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
  //     line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
  //     line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
  //     line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
  //     line_str.push(INDENT + INDENT + INDENT + `L.LDPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
  //     line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
  //     line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
  //     line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
  //     line_str.push(INDENT + INDENT + LF);      
    
  //     //////////////////////////////////////////////////
  //     // デフォルトのwhile
  //     //////////////////////////////////////////////////    
  //     var until = block.getFieldValue('MODE') == 'UNTIL';
  //     var argument0 = Blockly.Python.valueToCode(block, 'BOOL',
  //         until ? Blockly.Python.ORDER_LOGICAL_NOT :
  //         Blockly.Python.ORDER_NONE) || 'False';
  //     var branch = line_str.join("") + Blockly.Python.statementToCode(block, 'DO');
  //     if (until) {
  //       branch = 'if not ' + argument0 + ':\n' + Blockly.Python.prefixLines(branch, Blockly.Python.INDENT);
  //     }
  //     return branch;
  //     // return 'while ' + argument0 + ':\n' + branch;
  //  };


    python.pythonGenerator.forBlock['loop'] = function(block, generator) {
      //////////////////////////////////////////////////
      // アドレス参照
      //////////////////////////////////////////////////    
      const myBlock = self.getBlockAddr(block.customId);       
      //////////////////////////////////////////////////
      // シーケンス作成
      //////////////////////////////////////////////////
      let LF = '\n';
      let INDENT = '  ';
      let line_str = [];
      line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
        else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
      }
      if(myBlock.reset_addr_list){
        for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
      }
      if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      //////////////////////////////////////////////////
      // プロセス後動作
      //////////////////////////////////////////////////
      line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
      // action
      line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
      // Prev.ボタン対応
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] !== 992002){
          if (i === 0){
            line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
            line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
          }
          else{
            line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
          }
          line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
        }
      }
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `start_time = time.perf_counter()` + LF);
  
      
      line_str.push(INDENT + INDENT + LF);      
      var code = line_str.join("");

      // DOステートメント以降のブロックコードを取得
      var statements_do = python.pythonGenerator.statementToCode(block, 'DO');  
      // 各行の先頭のインデントを削除
      statements_do = statements_do.replace(/^ {2}/gm, '');   
      // statements_do.split('\n').forEach(function(statement) {
      //   code += statement + '\n';
      // });
      return code + statements_do;
  };

  python.pythonGenerator.forBlock['set_motor'] = function(block, generator) {
    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    var state = block.getFieldValue('state_list');
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////    
    const myBlock = self.getBlockAddr(block.customId); 
 
    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['servo_success[0]']['name'], L.local_MR['servo_success[0]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.AND(robot_status['servo'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    // timeout
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    // action
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT +`L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['servo_success[0]']['name'], L.local_MR['servo_success[0]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT +`if (L.aax & L.iix):` + LF);
    if(state === 'on') {
      line_str.push(INDENT + INDENT + INDENT + INDENT + `success = RAC.send_command('setServoOn()')` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `if (success): L.setRelay(L.local_MR['servo_success[0]']['name'], L.local_MR['servo_success[0]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `else        : L.resetRelay(L.local_MR['servo_success[0]']['name'], L.local_MR['servo_success[0]']['addr'])` + LF);
    }
    else if(state === 'off') {
      line_str.push(INDENT + INDENT + INDENT + INDENT + `success = RAC.send_command('setServoOff()')` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `if (success): L.setRelay(L.local_MR['servo_success[0]']['name'], L.local_MR['servo_success[0]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `else        : L.resetRelay(L.local_MR['servo_success[0]']['name'], L.local_MR['servo_success[0]']['addr'])` + LF);

    }
    line_str.push(INDENT + INDENT + LF);

    return line_str.join("");
  };

  python.pythonGenerator.forBlock['origin'] = function(block, generator) {
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////    
    const myBlock = self.getBlockAddr(block.customId); 
    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.AND(robot_status['origin'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    // timeout
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    // action
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT +`L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT +`if ((L.aax & L.iix) and not(robot_status['origin'])):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `RAC.send_command('moveOrigin()')` + LF); 
    line_str.push(INDENT + INDENT + LF);

    return line_str.join("");
  };

  python.pythonGenerator.forBlock['set_speed'] = function(block, generator) {
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////   
    const myBlock = self.getBlockAddr(block.customId); 
    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const program_override = block.getFieldValue('speed');
    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + `L.ANB(${self.addr_str}, ${myBlock.myBlock.reset_addr_list[i]})` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    // timeout
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);  
    }
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `program_override = ${program_override}` + LF);
    line_str.push(LF);              

    return line_str.join("");
  };

  python.pythonGenerator.forBlock['wait_ready'] = function(block, generator) {
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////    
    const myBlock = self.getBlockAddr(block.customId); 
    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(MR, 307)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LD(${self.buttonLampDevice}, ${self.buttonReadyAddr})` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   
    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    // action
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(MR, 0)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_T['500msec_timer[0]']['name'], L.local_T['500msec_timer[0]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(${self.buttonLampDevice}, ${self.lampReadyAddr})` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    // line_str.push(INDENT + INDENT + INDENT + INDENT + `sub_status.append("Press 'Ready' to proceed the program.")` + LF);
    // line_str.push(INDENT + INDENT + INDENT + INDENT + `L.EM_relay[0:0+len(helper.name_to_ascii16(sub_status, 40))] = helper.name_to_ascii16(sub_status, 40)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(MR, 600)` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    // line_str.push(INDENT + INDENT + INDENT + INDENT + `auto_status = 'Done READY.'` + LF);
    // line_str.push(INDENT + INDENT + INDENT + INDENT + `L.EM_relay[0:0+len(helper.name_to_ascii16(auto_status, 40))] = helper.name_to_ascii16(auto_status, 40)` + LF);
    line_str.push(INDENT + INDENT + LF);

    return line_str.join("");
  };

  python.pythonGenerator.forBlock['wait_run'] = function(block, generator) {
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////    
    const myBlock = self.getBlockAddr(block.customId); 
    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LD(${self.buttonLampDevice}, ${self.buttonRunAddr})` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   
    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    // action
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(MR, 2)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_T['500msec_timer[0]']['name'], L.local_T['500msec_timer[0]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(${self.buttonLampDevice}, ${self.lampRunAddr})` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    // line_str.push(INDENT + INDENT + INDENT + INDENT + `auto_status = 'Please press RUN.'` + LF);
    // line_str.push(INDENT + INDENT + INDENT + INDENT + `L.EM_relay[0:0+len(helper.name_to_ascii16(auto_status, 40))] = helper.name_to_ascii16(auto_status, 40)` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    // line_str.push(INDENT + INDENT + INDENT + INDENT + `auto_status = 'Auto Running ...'` + LF);
    // line_str.push(INDENT + INDENT + INDENT + INDENT + `L.EM_relay[0:0+len(helper.name_to_ascii16(auto_status, 40))] = helper.name_to_ascii16(auto_status, 40)` + LF);
    line_str.push(INDENT + INDENT + LF); 
    return line_str.join("");
  };

  python.pythonGenerator.forBlock['system_variable'] = function(block, generator) {
    const name = block.getFieldValue('name');
    let code = undefined;

    if (name === 'input')       code = `helper.uint16s_to_int32(L.EM_relay[2003], L.EM_relay[2004])`;
    else if (name === 'output') code = `helper.uint16s_to_int32(L.EM_relay[2023], L.EM_relay[2024])`;
    
    // L.EM_relay[2003:2004] = helper.int32_to_uint16s(1000)

    return [code, generator.ORDER_ATOMIC]; //数値や式として扱う場合は [code, Blockly.Python.ORDER_ATOMIC] を使う
  };

  python.pythonGenerator.forBlock['set_system_variable'] = function(block, generator) {    
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////   
    const myBlock = self.getBlockAddr(block.customId); 
 

    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const name = block.getFieldValue('name');
    const inputValue = generator.valueToCode(block, 'right_hand_side', generator.ORDER_ATOMIC) || '0';
    const rightHandSide =`helper.int32_to_uint16s(${inputValue})`;
    let lefttHandSide = undefined;
    if (name === 'input')       lefttHandSide = `L.EM_relay[2003:2004+1]`;
    else if (name === 'output') lefttHandSide = `L.EM_relay[2023:2024+1]`;

    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + `L.ANB(${self.addr_str}, ${myBlock.myBlock.reset_addr_list[i]})` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF); 

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `${lefttHandSide} = ${rightHandSide}` + LF);

    line_str.push(INDENT + INDENT + LF);      

    return line_str.join("");
};

  python.pythonGenerator.forBlock['set_flag'] = function(block, generator) {    
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////   
    const myBlock = self.getBlockAddr(block.customId); 
 

    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const name = block.getFieldValue('name');
    const rightHandSide = generator.valueToCode(block, 'right_hand_side', generator.ORDER_ATOMIC) || '0';
    const lefttHandSide = `flag_param_yaml['${name}']['value']`;

    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + `L.ANB(${self.addr_str}, ${myBlock.myBlock.reset_addr_list[i]})` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF); 

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `${lefttHandSide} = ${rightHandSide}` + LF);

    line_str.push(INDENT + INDENT + LF);      

    return line_str.join("");
  };

  python.pythonGenerator.forBlock['set_flag_upon'] = function(block, generator) {    
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////   
    const myBlock = self.getBlockAddr(block.customId); 
 

    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const name = block.getFieldValue('name');
    const rightHandSide = generator.valueToCode(block, 'right_hand_side', generator.ORDER_ATOMIC) || '0';
    const lefttHandSide = `flag_param_yaml['${name}']['value']`;
    const condition = generator.valueToCode(block, 'condition', generator.ORDER_ATOMIC) || '0';
    const triggerSate = block.getFieldValue('trigger_condition');

    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${condition}) else False)` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // 100msecパルス
    if      (triggerSate === 'steady')  {
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `${lefttHandSide} = ${rightHandSide}` + LF);

    }
    else if (triggerSate === 'rising')  {
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `${lefttHandSide} = ${rightHandSide}` + LF);
    }
    else if (triggerSate === 'falling') {
      line_str.push(INDENT + INDENT + INDENT + `L.LDF(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `${lefttHandSide} = ${rightHandSide}` + LF);
    }
    return line_str.join("");
  };


  python.pythonGenerator.forBlock['set_output_during'] = function(block, generator) {
    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const out_pin_no = block.getFieldValue('output_pin_name');
    const state = block.getFieldValue('output_state');
    const name = block.getFieldValue('name');
    const timer = `number_param_yaml['${name}']['value']`;
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////    
    const myBlock = self.getBlockAddr(block.customId); 
 
    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_T['block_timer1[${myBlock.index}]']['name'], L.local_T['block_timer1[${myBlock.index}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    // timeout
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if ((L.aax & L.iix) and (RAC.connected)):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    // action
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if ((L.aax & L.iix) and (RAC.connected)):` + LF);
    if      (state === 'on')  {
      line_str.push(INDENT + INDENT + INDENT + INDENT + `success = RAC.send_command('setOutputON(${out_pin_no})')` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + `if (success): L.setRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + `else        : L.resetRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
    } 
    else if (state === 'off') {
      line_str.push(INDENT + INDENT + INDENT + INDENT + `success = RAC.send_command('setOutputOFF(${out_pin_no})')` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + `if (success): L.setRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + `else        : L.resetRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timer1[${myBlock.index}]']['addr'], wait_msec=${timer})` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timer1[${myBlock.index}]']['name'], L.local_T['block_timer1[${myBlock.index}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if ((L.aax & L.iix) and (RAC.connected)):` + LF);
    if      (state === 'on')  line_str.push(INDENT + INDENT + INDENT + INDENT + `RAC.send_command('setOutputOFF(${out_pin_no})')` + LF); 
    else if (state === 'off') line_str.push(INDENT + INDENT + INDENT + INDENT + `RAC.send_command('setOutputON(${out_pin_no})')` + LF); 
    // line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    // line_str.push(INDENT + INDENT + INDENT + INDENT + `L.resetRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + LF);

    return line_str.join("");
  };

  python.pythonGenerator.forBlock['set_output'] = function(block, generator) {
    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const out_pin_no = block.getFieldValue('output_pin_name');
    const out_state = block.getFieldValue('out_state');
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////    
    const myBlock = self.getBlockAddr(block.customId); 
 
    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    // timeout
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if ((L.aax & L.iix) and (RAC.connected)):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    // action
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if ((L.aax & L.iix) and (RAC.connected)):` + LF);
    if      (out_state === 'on')  {
      line_str.push(INDENT + INDENT + INDENT + INDENT + `success = RAC.send_command('setOutputON(${out_pin_no})')` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + `if (success): L.setRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + `else        : L.resetRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
    } 
    else if (out_state === 'off') {
      line_str.push(INDENT + INDENT + INDENT + INDENT + `success = RAC.send_command('setOutputOFF(${out_pin_no})')` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + `if (success): L.setRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + `else        : L.resetRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
    }
    // line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    // line_str.push(INDENT + INDENT + INDENT + INDENT + `L.resetRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + LF);

    return line_str.join("");
  };

  python.pythonGenerator.forBlock['set_output_until'] = function(block, generator) {
    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const out_pin_no = block.getFieldValue('output_pin_name');
    const out_state = block.getFieldValue('out_state');
    const in_pin_no = block.getFieldValue('input_pin_name');
    const in_state = block.getFieldValue('input_state');
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////    
    const myBlock = self.getBlockAddr(block.customId); 
 
    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    if      (in_state === 'none')  line_str.push(INDENT + INDENT + INDENT + `L.AND(True)` + LF); 
    else if (in_state === 'on')    line_str.push(INDENT + INDENT + INDENT + `L.AND(True if robot_status['input_signal'][${in_pin_no}] else False)` + LF); 
    else if (in_state === 'off')   line_str.push(INDENT + INDENT + INDENT + `L.AND(False if robot_status['input_signal'][${in_pin_no}] else True)` + LF);     
    // line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    // timeout
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if ((L.aax & L.iix) and (RAC.connected)):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    // action
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if ((L.aax & L.iix) and (RAC.connected)):` + LF);
    if      (out_state === 'on')  {
      line_str.push(INDENT + INDENT + INDENT + INDENT + `success = RAC.send_command('setOutputON(${out_pin_no})')` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + `if (success): L.setRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + `else        : L.resetRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
    } 
    else if (out_state === 'off') {
      line_str.push(INDENT + INDENT + INDENT + INDENT + `success = RAC.send_command('setOutputOFF(${out_pin_no})')` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + `if (success): L.setRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + `else        : L.resetRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if ((L.aax & L.iix) and (RAC.connected)):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `RAC.send_command('getInput(${in_pin_no})')` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    if (in_state === 'on')         line_str.push(INDENT + INDENT + INDENT + `L.AND(True if robot_status['input_signal'][${in_pin_no}] else False)` + LF); 
    else if (in_state === 'off')   line_str.push(INDENT + INDENT + INDENT + `L.AND(False if robot_status['input_signal'][${in_pin_no}] else True)` + LF);   
    // line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if ((L.aax & L.iix) and (RAC.connected)):` + LF);
    if      (out_state === 'on')  line_str.push(INDENT + INDENT + INDENT + INDENT + `RAC.send_command('setOutputOFF(${out_pin_no})')` + LF); 
    else if (out_state === 'off') line_str.push(INDENT + INDENT + INDENT + INDENT + `RAC.send_command('setOutputON(${out_pin_no})')` + LF);
    // line_str.push(INDENT + INDENT + INDENT + INDENT + `L.resetRelay(L.local_MR['robot_io_success[0]']['name'], L.local_MR['robot_io_success[0]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + LF);

    return line_str.join("");
  };

  python.pythonGenerator.forBlock['wait_input'] = function(block, generator) {
    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const in_pin_no = block.getFieldValue('input_pin_name');
    const in_state = block.getFieldValue('input_state');
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////    
    const myBlock = self.getBlockAddr(block.customId); 
 
    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    if      (in_state === 'none')  line_str.push(INDENT + INDENT + INDENT + `L.AND(True)` + LF); 
    else if (in_state === 'on')    line_str.push(INDENT + INDENT + INDENT + `L.AND(True if robot_status['input_signal'][${in_pin_no}] else False)` + LF); 
    else if (in_state === 'off')    line_str.push(INDENT + INDENT + INDENT + `L.AND(False if robot_status['input_signal'][${in_pin_no}] else True)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   
    // timeout
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    // action
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `RAC.send_command('getInput(${in_pin_no})')` + LF);
    line_str.push(INDENT + INDENT + LF);
    
    return line_str.join("");
  };

  python.pythonGenerator.forBlock['set_pallet'] = function(block, generator) {
    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    let pallet_no = block.getFieldValue('no_list');
    let pallet_row = block.getFieldValue('row_list');
    let pallet_col = block.getFieldValue('col_list');
    let point_A_name = block.getFieldValue('A_name_list');
    let point_B_name = block.getFieldValue('B_name_list');
    let point_C_name = block.getFieldValue('C_name_list');
    let point_D_name = block.getFieldValue('D_name_list');
    let reseted_value = block.getFieldValue('reseted_value');
    // オフセット量計算に必要なデータを、パレットブロックから取得
    let point_A = [];
    let point_A_name_str = String(point_A_name);
    point_A.x = self.blockUtilsIns.teachingJson[point_A_name_str]['x_pos'];
    point_A.y = self.blockUtilsIns.teachingJson[point_A_name_str]['y_pos'];
    point_A.z = self.blockUtilsIns.teachingJson[point_A_name_str]['z_pos'];
    let point_B = [];
    let point_B_name_str = String(point_B_name);
    point_B.x = self.blockUtilsIns.teachingJson[point_B_name_str]['x_pos'];
    point_B.y = self.blockUtilsIns.teachingJson[point_B_name_str]['y_pos'];
    point_B.z = self.blockUtilsIns.teachingJson[point_B_name_str]['z_pos'];
    let point_C = [];
    let point_C_name_str = String(point_C_name);
    point_C.x = self.blockUtilsIns.teachingJson[point_C_name_str]['x_pos'];
    point_C.y = self.blockUtilsIns.teachingJson[point_C_name_str]['y_pos'];
    point_C.z = self.blockUtilsIns.teachingJson[point_C_name_str]['z_pos'];
    let point_D = [];
    let point_D_name_str = String(point_D_name);
    point_D.x = self.blockUtilsIns.teachingJson[point_D_name_str]['x_pos'];
    point_D.y = self.blockUtilsIns.teachingJson[point_D_name_str]['y_pos'];
    point_D.z = self.blockUtilsIns.teachingJson[point_D_name_str]['z_pos'];
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////    
    const myBlock = self.getBlockAddr(block.customId); 
 
    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    // timeout
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    // action
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `contents = {}` + LF);
    // line_str.push(INDENT + INDENT + INDENT + INDENT + `contents['dst_pocket'] = 1` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `contents['row'] = ${pallet_row}` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `contents['col'] = ${pallet_col}` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `contents['reseted_value'] = '${reseted_value}'` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `contents['A'] = {'x':${point_A.x}, 'y':${point_A.y}, 'z':${point_A.z}}` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `contents['B'] = {'x':${point_B.x}, 'y':${point_B.y}, 'z':${point_B.z}}` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `contents['C'] = {'x':${point_C.x}, 'y':${point_C.y}, 'z':${point_C.z}}` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `contents['D'] = {'x':${point_D.x}, 'y':${point_D.y}, 'z':${point_D.z}}` + LF);
    if (reseted_value === 'max')       line_str.push(INDENT + INDENT + INDENT + INDENT + `contents['dst_pocket'] = (${pallet_row}*${pallet_col}) - (L.EM_relay[3300+((${pallet_no}-1)*10)]-1)` + LF);
    else if (reseted_value === 'zero') line_str.push(INDENT + INDENT + INDENT + INDENT + `contents['dst_pocket'] = L.EM_relay[3300+((${pallet_no}-1)*10)] + 1` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `pallet_settings[${pallet_no}-1] = contents.copy()` + LF);
    // line_str.push(INDENT + INDENT + INDENT + INDENT + `number_param_yaml['N'+str(490+${pallet_no}-1)]['value'] = pallet_settings[${pallet_no}-1]['row'] * pallet_settings[${pallet_no}-1]['col']` + LF);
    // if(reseted_value === "max")       line_str.push(INDENT + INDENT + INDENT + INDENT + `number_param_yaml['N'+str(490+${pallet_no}-1)]['value'] = pallet_settings[${pallet_no}-1]['row'] * pallet_settings[${pallet_no}-1]['col']` + LF);
    // else if(reseted_value === "zero") line_str.push(INDENT + INDENT + INDENT + INDENT + `if (pallet_settings[${pallet_no}-1]['reseted_value'] == 'zero'): number_param_yaml['N'+str(490+${pallet_no}-1)]['value'] = 0` + LF);
    // line_str.push(INDENT + INDENT + INDENT + INDENT + `number_param_yaml['N'+str(490+${pallet_no}-1)]['value'] = L.EM_relay[3300+((${pallet_no}-1)*10)]` + LF);
    // line_str.push(INDENT + INDENT + INDENT + INDENT + `L.EM_relay[3300+((${pallet_no}-1)*10)] = number_param_yaml['N'+str(490+${pallet_no}-1)]['value']` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    if (reseted_value === 'max') line_str.push(INDENT + INDENT + INDENT + INDENT + `pallet_settings[${pallet_no}-1]['dst_pocket'] = (${pallet_row}*${pallet_col}) - (L.EM_relay[3300+((${pallet_no}-1)*10)]-1)` + LF);
    else if (reseted_value === 'zero') line_str.push(INDENT + INDENT + INDENT + INDENT + `pallet_settings[${pallet_no}-1]['dst_pocket'] = L.EM_relay[3300+((${pallet_no}-1)*10)] + 1` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `number_param_yaml['N'+str(490+${pallet_no}-1)]['value'] = L.EM_relay[3300+((${pallet_no}-1)*10)]` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `pallet_offset[${pallet_no}-1] = drive.getPalletOffset(pallet_settings, ${pallet_no}-1)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 1701)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    if (reseted_value === 'max') line_str.push(INDENT + INDENT + INDENT + INDENT + `L.EM_relay[3300+((${pallet_no}-1)*10)] = ${pallet_row} * ${pallet_col}` + LF);
    else if (reseted_value === 'zero') line_str.push(INDENT + INDENT + INDENT + INDENT + `L.EM_relay[3300+((${pallet_no}-1)*10)] = 0` + LF);
    line_str.push(INDENT + INDENT + LF);

    return line_str.join("");
  };

  python.pythonGenerator.forBlock['move_next_pallet'] = function(block, generator) {
    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    let pallet_no = block.getFieldValue('no_list');
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////    
    const myBlock = self.getBlockAddr(block.customId); 
 
    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    // timeout
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    // action
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}+0, message="${block.customId}:Can't move next the numbers in pallet No.${pallet_no}.", error_yaml=error_yaml)` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `MAX_row = pallet_settings[${pallet_no}-1]['row']` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `MAX_col = pallet_settings[${pallet_no}-1]['col']` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `reseted_value = pallet_settings[${pallet_no}-1]['reseted_value']` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `dst_pocket = pallet_settings[${pallet_no}-1]['dst_pocket']` + LF);
    // line_str.push(INDENT + INDENT + INDENT + INDENT + `dst_pocket = (MAX_row*MAX_col) - (L.EM_relay[3300+((${pallet_no}-1)*10)]-1)` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `if ((dst_pocket <= MAX_row * MAX_col) and (dst_pocket > 0)):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `if (reseted_value == 'max'): L.EM_relay[3300+((${pallet_no}-1)*10)] = L.EM_relay[3300+((${pallet_no}-1)*10)] - 1` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `if (reseted_value == 'zero'): L.EM_relay[3300+((${pallet_no}-1)*10)] = L.EM_relay[3300+((${pallet_no}-1)*10)] + 1` + LF);
    // line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `if (reseted_value == 'max'): number_param_yaml['N'+str(490+${pallet_no}-1)]['value'] = (MAX_row*MAX_col) - dst_pocket` + LF);
    // line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `if (reseted_value == 'zero'): number_param_yaml['N'+str(490+${pallet_no}-1)]['value'] = dst_pocket` + LF);
    // line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `L.EM_relay[3300+((${pallet_no}-1)*10)] = number_param_yaml['N'+str(490+${pallet_no}-1)]['value']` + LF);
    // line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `pallet_settings[${pallet_no}-1]['dst_pocket'] = dst_pocket + 1` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `else:` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}+0, error_yaml=error_yaml)` + LF);
    line_str.push(INDENT + INDENT + LF);

    return line_str.join("");
  };

  python.pythonGenerator.forBlock['reset_pallet'] = function(block, generator) {
    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    let pallet_no = block.getFieldValue('no_list');
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////    
    const myBlock = self.getBlockAddr(block.customId); 
    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    // timeout
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    // action
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `MAX_row = pallet_settings[${pallet_no}-1]['row']` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `MAX_col = pallet_settings[${pallet_no}-1]['col']` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `reseted_value = pallet_settings[${pallet_no}-1]['reseted_value']` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `if (reseted_value == 'max'): L.EM_relay[3300+((${pallet_no}-1)*10)] = MAX_row * MAX_col` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `if (reseted_value == 'zero'): L.EM_relay[3300+((${pallet_no}-1)*10)] = 0` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `pallet_settings[${pallet_no}-1]['dst_pocket'] = 1` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `pallet_offset[${pallet_no}-1] = {'x': 0.0, 'y': 0.0, 'z': 0.0}` + LF);
    line_str.push(INDENT + INDENT + LF);

    return line_str.join("");
  };

  python.pythonGenerator.forBlock['controls_if'] = function(block, generator) {

    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////    
    const myBlock = self.getBlockAddr(block.customId); 
 

    //////////////////////////////////////////////////
    // プロセス前動作
    ////////////////////////////////////////////////// 
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Pre-Process:` + block.customId + LF);
    const IF0 = generator.valueToCode(block, 'IF0', generator.ORDER_ATOMIC) || '0';
    const IF1 = generator.valueToCode(block, 'IF1', generator.ORDER_ATOMIC) || '0';
    const IF2 = generator.valueToCode(block, 'IF2', generator.ORDER_ATOMIC) || '0';
    const IF3 = generator.valueToCode(block, 'IF3', generator.ORDER_ATOMIC) || '0';
    const IF4 = generator.valueToCode(block, 'IF4', generator.ORDER_ATOMIC) || '0';
    const IF5 = generator.valueToCode(block, 'IF5', generator.ORDER_ATOMIC) || '0';
    const IF6 = generator.valueToCode(block, 'IF6', generator.ORDER_ATOMIC) || '0';
    const IF7 = generator.valueToCode(block, 'IF7', generator.ORDER_ATOMIC) || '0';
    const IF8 = generator.valueToCode(block, 'IF8', generator.ORDER_ATOMIC) || '0';

    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset2[${myBlock.index}]']['name'], L.local_MR['seq_step_reset2[${myBlock.index}]']['addr'])` + LF); 
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset3[${myBlock.index}]']['name'], L.local_MR['seq_step_reset3[${myBlock.index}]']['addr'])` + LF); 
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset4[${myBlock.index}]']['name'], L.local_MR['seq_step_reset4[${myBlock.index}]']['addr'])` + LF); 
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset5[${myBlock.index}]']['name'], L.local_MR['seq_step_reset5[${myBlock.index}]']['addr'])` + LF); 
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset6[${myBlock.index}]']['name'], L.local_MR['seq_step_reset6[${myBlock.index}]']['addr'])` + LF); 
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset7[${myBlock.index}]']['name'], L.local_MR['seq_step_reset7[${myBlock.index}]']['addr'])` + LF); 
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset8[${myBlock.index}]']['name'], L.local_MR['seq_step_reset8[${myBlock.index}]']['addr'])` + LF); 
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset9[${myBlock.index}]']['name'], L.local_MR['seq_step_reset9[${myBlock.index}]']['addr'])` + LF); 
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset10[${myBlock.index}]']['name'], L.local_MR['seq_step_reset10[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);

    // 条件分岐有（出力10つ）
    if (myBlock.stop10_addr){
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop10_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop10_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF0}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop10_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop10_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF1}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop10_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop10_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF2}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop10_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop10_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF3}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop10_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop10_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF4}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop10_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop10_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF5}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop10_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop10_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF6}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop10_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop10_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF7}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop10_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop10_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF8}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop10_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop10_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      if (IF8 !== '0') line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF8}) else False)` + LF);
      else line_str.push(INDENT + INDENT + INDENT + `L.LD(not(True if ((${IF0}) and (${IF1}) and (${IF2}) and (${IF3}) and (${IF4}) and (${IF5}) and (${IF6}) and (${IF7}) and (${IF8})) else False))` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop10_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop10_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop10_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop10_addr}]']['addr'])` + LF);   
    }
    // 条件分岐有（出力9つ）
    else if (myBlock.stop9_addr){
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF0}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF1}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF2}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF3}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF4}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF5}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF6}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF7}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      if (IF8 !== '0') line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF8}) else False)` + LF);
      else line_str.push(INDENT + INDENT + INDENT + `L.LD(not(True if ((${IF0}) and (${IF1}) and (${IF2}) and (${IF3}) and (${IF4}) and (${IF5}) and (${IF6}) and (${IF7})) else False))` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop9_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop9_addr}]']['addr'])` + LF);   
    }
    // 条件分岐有（出力8つ）
    else if (myBlock.stop8_addr){
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF0}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF1}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF2}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF3}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF4}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF5}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF6}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      if (IF7 !== '0') line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF7}) else False)` + LF);
      else line_str.push(INDENT + INDENT + INDENT + `L.LD(not(True if ((${IF0}) and (${IF1}) and (${IF2}) and (${IF3}) and (${IF4}) and (${IF5}) and (${IF6})) else False))` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop8_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop8_addr}]']['addr'])` + LF);   
    }
    // 条件分岐有（出力7つ）
    else if (myBlock.stop7_addr){
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF0}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF1}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF2}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF3}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF4}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF5}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      if (IF6 !== '0') line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF6}) else False)` + LF);
      else line_str.push(INDENT + INDENT + INDENT + `L.LD(not(True if ((${IF0}) and (${IF1}) and (${IF2}) and (${IF3}) and (${IF4}) and (${IF5})) else False))` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop7_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop7_addr}]']['addr'])` + LF);   
    }
    // 条件分岐有（出力6つ）
    else if (myBlock.stop6_addr){
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF0}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF1}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF2}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF3}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF4}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      if (IF5 !== '0') line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF5}) else False)` + LF);
      else line_str.push(INDENT + INDENT + INDENT + `L.LD(not(True if ((${IF0}) and (${IF1}) and (${IF2}) and (${IF3}) and (${IF4})) else False))` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop6_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop6_addr}]']['addr'])` + LF);   
    }
    // 条件分岐有（出力5つ）
    else if (myBlock.stop5_addr){
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF0}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF1}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF2}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF3}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      if (IF4 !== '0') line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF4}) else False)` + LF);
      else line_str.push(INDENT + INDENT + INDENT + `L.LD(not(True if ((${IF0}) and (${IF1}) and (${IF2}) and (${IF3})) else False))` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop5_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop5_addr}]']['addr'])` + LF);   
    }
    // 条件分岐有（出力4つ）
    else if (myBlock.stop4_addr){
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF0}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF1}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF2}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      if (IF3 !== '0') line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF3}) else False)` + LF);
      else line_str.push(INDENT + INDENT + INDENT + `L.LD(not(True if ((${IF0}) and (${IF1}) and (${IF2})) else False))` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop4_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop4_addr}]']['addr'])` + LF);   
    }
    // 条件分岐有（出力3つ）
    else if (myBlock.stop3_addr){
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF0}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF1}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      if (IF2 !== '0') line_str.push(INDENT + INDENT + INDENT + `L.LD(not(True if (${IF2}) else False))` + LF);
      else line_str.push(INDENT + INDENT + INDENT + `L.LD(not(True if ((${IF0}) and (${IF1})) else False))` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop3_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop3_addr}]']['addr'])` + LF);   
    }
    // 条件分岐有（出力2つ）
    else if (myBlock.stop2_addr){
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MRD()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF0}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      if (IF1 !== '0') line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF1}) else False)` + LF);
      else line_str.push(INDENT + INDENT + INDENT + `L.LD(not(True if (${IF0}) else False))` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop2_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop2_addr}]']['addr'])` + LF);   
    }
    // 条件分岐無（出力1つ）
    else {
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${IF0}) else False)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   
    }

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }

    line_str.push(INDENT + INDENT + LF);

    //ネストされたブロックの先頭空白を2つ分削除
    // var condition = generator.statementToCode(block, 'CONDITION');
    var branches = ['DO0', 'DO1', 'DO2', 'DO3', 'DO4', 'DO5', 'DO6', 'DO7', 'DO8', 'ELSE'].map(label => generator.statementToCode(block, label)).join('\n');

    return line_str.join("") + branches.replace(/^ {2}/gm, ''); 
  };

  python.pythonGenerator.forBlock['raise_error'] = function(block, generator) {
      //////////////////////////////////////////////////
      // アドレス参照
      //////////////////////////////////////////////////   
      const myBlock = self.getBlockAddr(block.customId); 

      //////////////////////////////////////////////////
      // 前処理
      //////////////////////////////////////////////////
      const message = block.getFieldValue('error_message');

      //////////////////////////////////////////////////
      // プロセス
      //////////////////////////////////////////////////
      let LF = '\n';
      let INDENT = '  ';
      let line_str = [];
      line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
        else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
      }
      if(myBlock.reset_addr_list){
        for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + `L.ANB(${self.addr_str}, ${myBlock.myBlock.reset_addr_list[i]})` + LF);
      }
      if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF); 

      //////////////////////////////////////////////////
      // プロセス後動作
      //////////////////////////////////////////////////
      line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
      if (Number(block.timeoutMillis) !== -1){
        line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);  
      }
      line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
      // Prev.ボタン対応
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] !== 992002){
          if (i === 0){
            line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
            line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
          }
          else{
            line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
          }
          line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
        }
      }
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message="${message}", error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + LF);      

      return line_str.join("");
};

  python.pythonGenerator.forBlock['raise_error_upon'] = function(block, generator) {
      //////////////////////////////////////////////////
      // アドレス参照
      //////////////////////////////////////////////////   
      const myBlock = self.getBlockAddr(block.customId); 

      //////////////////////////////////////////////////
      // 前処理
      //////////////////////////////////////////////////
      const condition = generator.valueToCode(block, 'condition', generator.ORDER_ATOMIC) || '0';
      const message = block.getFieldValue('error_message');
      const triggerSate = block.getFieldValue('trigger_condition');

      //////////////////////////////////////////////////
      // プロセス
      //////////////////////////////////////////////////
      let LF = '\n';
      let INDENT = '  ';
      let line_str = [];
      line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(True if ${condition} else False)` + LF);
      // line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
        else line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
      }
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      //////////////////////////////////////////////////
      // プロセス後動作
      //////////////////////////////////////////////////
      line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);   
      if      (triggerSate === 'steady')  line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      else if (triggerSate === 'rising')  line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      else if (triggerSate === 'falling') line_str.push(INDENT + INDENT + INDENT + `L.LDF(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message="${message}", error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);

      // line_str.push(INDENT + INDENT + INDENT + INDENT + `try:` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${block.blockNo}-1, error_yaml=error_yaml)` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + `except ValueError as e:` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `print(f"Error:${block.customId}: {e}")` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + `else:` + LF);
      // line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `pass` + LF);

      //////////////////////////////////////////////////
      // プロセス
      //////////////////////////////////////////////////
      // line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);

      return line_str.join("");
  };

  python.pythonGenerator.forBlock['stop_robot_upon'] = function(block, generator) {
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////   
    const myBlock = self.getBlockAddr(block.customId); 
 

    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const condition = generator.valueToCode(block, 'condition', generator.ORDER_ATOMIC) || '0';
    const triggerSate = block.getFieldValue('trigger_condition');

    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${condition}) else False)` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // 100msecパルス
    if      (triggerSate === 'steady')  {
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_R['external_pausing[0]']['name'], L.local_R['external_pausing[0]']['addr'])` + LF);
    }
    else if (triggerSate === 'rising')  {
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `L.setRelay(L.local_R['external_pausing[0]']['name'], L.local_R['external_pausing[0]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], 100)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `L.resetRelay(L.local_R['external_pausing[0]']['name'], L.local_R['external_pausing[0]']['addr'])` + LF);    
    }
    else if (triggerSate === 'falling') {
      line_str.push(INDENT + INDENT + INDENT + `L.LDF(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `L.setRelay(L.local_R['external_pausing[0]']['name'], L.local_R['external_pausing[0]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], 100)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `L.resetRelay(L.local_R['external_pausing[0]']['name'], L.local_R['external_pausing[0]']['addr'])` + LF);
    }

    return line_str.join("");
};

  python.pythonGenerator.forBlock['wait_block'] = function(block, generator) {
      //////////////////////////////////////////////////
      // アドレス参照
      //////////////////////////////////////////////////    
      const myBlock = self.getBlockAddr(block.customId); 
      //////////////////////////////////////////////////
      // 前処理
      //////////////////////////////////////////////////
      const condition = generator.valueToCode(block, 'condition', generator.ORDER_ATOMIC) || '0';
      //////////////////////////////////////////////////
      // プロセス
      //////////////////////////////////////////////////
      let LF = '\n';
      let INDENT = '  ';
      let line_str = [];
      line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] === 992002){
          line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
        }
        else line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
      }
      if(myBlock.reset_addr_list){
        for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
      }
      if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.AND(${condition})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   
      line_str.push(INDENT + INDENT + INDENT + LF);   

      //////////////////////////////////////////////////
      // プロセス後動作
      //////////////////////////////////////////////////
      // timeout
      if (Number(block.timeoutMillis) !== -1){
        line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);  
      }
      // action
      line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
      // Prev.ボタン対応
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] !== 992002){
          if (i === 0){
            line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
            line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
          }
          else{
            line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
          }
          line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
        }
      }

    return line_str.join("");
};

  python.pythonGenerator.forBlock['math_custom_number'] = function(block, generator) {
    const name = block.getFieldValue('name');
    // const param = self.blockUtilsIns.parameterJson[name]['value'];
    const code = `number_param_yaml['${name}']['value']`;
    
    return [code, generator.ORDER_ATOMIC]; //数値や式として扱う場合は [code, Blockly.Python.ORDER_ATOMIC] を使う
  };

  python.pythonGenerator.forBlock['set_number'] = function(block, generator) {    
      //////////////////////////////////////////////////
      // アドレス参照
      //////////////////////////////////////////////////   
      const myBlock = self.getBlockAddr(block.customId); 

      //////////////////////////////////////////////////
      // 前処理
      //////////////////////////////////////////////////
      const name = block.getFieldValue('name');
      const rightHandSide = generator.valueToCode(block, 'right_hand_side', generator.ORDER_ATOMIC) || '0';
      const lefttHandSide = `number_param_yaml['${name}']['value']`;

      //////////////////////////////////////////////////
      // プロセス
      //////////////////////////////////////////////////
      let LF = '\n';
      let INDENT = '  ';
      let line_str = [];
      line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
        else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
      }
      if(myBlock.reset_addr_list){
        for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + `L.ANB(${self.addr_str}, ${myBlock.myBlock.reset_addr_list[i]})` + LF);
      }
      if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF); 

      //////////////////////////////////////////////////
      // プロセス後動作
      //////////////////////////////////////////////////
      line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
      if (Number(block.timeoutMillis) !== -1){
        line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
        line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
        line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
        line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);  
      }
      line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
      // Prev.ボタン対応
      for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
        if(myBlock.survival1_addr_list[i] !== 992002){
          if (i === 0){
            line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
            line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
          }
          else{
            line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
          }
          line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
        }
      }
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `${lefttHandSide} = ${rightHandSide}` + LF);

      line_str.push(INDENT + INDENT + LF);      

      return line_str.join("");
  };

  python.pythonGenerator.forBlock['set_number_upon'] = function(block, generator) {    
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////   
    const myBlock = self.getBlockAddr(block.customId); 
 

    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const name = block.getFieldValue('name');
    const rightHandSide = generator.valueToCode(block, 'right_hand_side', generator.ORDER_ATOMIC) || '0';
    const lefttHandSide = `number_param_yaml['${name}']['value']`;
    const condition = generator.valueToCode(block, 'condition', generator.ORDER_ATOMIC) || '0';
    const triggerSate = block.getFieldValue('trigger_condition');

    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LD(True if (${condition}) else False)` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // 100msecパルス
    if      (triggerSate === 'steady')  {
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `${lefttHandSide} = ${rightHandSide}` + LF);

    }
    else if (triggerSate === 'rising')  {
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `${lefttHandSide} = ${rightHandSide}` + LF);
    }
    else if (triggerSate === 'falling') {
      line_str.push(INDENT + INDENT + INDENT + `L.LDF(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `${lefttHandSide} = ${rightHandSide}` + LF);
    }
    return line_str.join("");
};


  python.pythonGenerator.forBlock['logic_block'] = function(block, generator) {

    const blockNo = block.getFieldValue('block_no');
    const blockType = block.getFieldValue('block_type');
    const blockStatus = block.getFieldValue('block_status');
    let addr = null;
    let code = '';

    // 対象のブロックを探索
    for (let i = 0; i < self.blockUtilsIns.all_block_flow.length; i++) {
      for (let j = 0; j < self.blockUtilsIns.all_block_flow[i].length; j++) {
        if (self.blockUtilsIns.all_block_flow[i][j].custom_id === `${blockType}@${blockNo}`){
          if (blockStatus === 'start'){
            addr = self.blockUtilsIns.all_block_flow[i][j].start;
          }
          else if (blockStatus === 'stop'){
            addr = self.blockUtilsIns.all_block_flow[i][j].stop1;
          }
          break;
        }
      }
    }
    // 対象のブロックが見つかれば
    if (addr){
      code = `L.getRelay(L.local_MR['seq_step[${addr}]']['name'], L.local_MR['seq_step[${addr}]']['addr'])`;
    }
    
    return [code, generator.ORDER_ATOMIC]; //数値や式として扱う場合は [code, Blockly.Python.ORDER_ATOMIC] を使う
  };


  python.pythonGenerator.forBlock['logic_custom_flag'] = function(block, generator) {
    const name = block.getFieldValue('name');
    const code = `flag_param_yaml['${name}']['value']`;  

    return [code, generator.ORDER_ATOMIC]; //数値や式として扱う場合は [code, Blockly.Python.ORDER_ATOMIC] を使う
  };

  python.pythonGenerator.forBlock['robot_io'] = function(block, generator) {
    const in_pin_no = block.getFieldValue('input_pin_name');
    const code = `(robot_status['input_signal'][${in_pin_no}] if RAC.send_command('getInput(${in_pin_no})') else robot_status['input_signal'][${in_pin_no}])`;     
    return [code, generator.ORDER_ATOMIC];
  };

  python.pythonGenerator.forBlock['robot_position'] = function(block, generator) {
    const axis = block.getFieldValue('axis');
    const code = `current_pos['${axis}']`;     
    return [code, generator.ORDER_ATOMIC];
  };

  python.pythonGenerator.forBlock['connect_external_io'] = function(block, generator) {
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////   
    const myBlock = self.getBlockAddr(block.customId); 
 

    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const deviceName = block.getFieldValue('devive_name');
    const externalMaker = block.getFieldValue('external_maker');
    const ioNo = block.getFieldValue('io_no');

    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + `L.ANB(${self.addr_str}, ${myBlock.myBlock.reset_addr_list[i]})` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.AND(external_io_connected[0])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    // timeout
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    // action
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT +`L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT +`if (L.aax & L.iix):` + LF);
    if (externalMaker === "contec"){
      line_str.push(INDENT + INDENT + INDENT + INDENT + `external_io_instance[${ioNo}-1] = cdio_api` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `external_io_connected[${ioNo}-1] = external_io_instance[${ioNo}-1].init("${deviceName}")` + LF);
    }
    // error
    line_str.push(INDENT + INDENT + INDENT + `#;error:` + block.customId + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `if (external_io_connected[${ioNo}-1] == False):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}+0, message=f"${block.customId}:Connection is failed.", error_yaml=error_yaml)` + LF);  
    line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}+0, error_yaml=error_yaml)` + LF); 
    line_str.push(LF);      

    return line_str.join("");
  };

  python.pythonGenerator.forBlock['wait_external_io_input'] = function(block, generator) {
    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const ioNo = block.getFieldValue('io_no');
    const inPinNo = block.getFieldValue('input_pin_name');
    const inState = block.getFieldValue('in_state');
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////    
    const myBlock = self.getBlockAddr(block.customId); 
 
    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    if      (inState === 'none')  line_str.push(INDENT + INDENT + INDENT + `L.AND(True)` + LF); 
    else if (inState === 'on') line_str.push(INDENT + INDENT + INDENT + `L.AND(False if not hasattr(external_io_instance[${ioNo}-1], 'get_input') else (True if external_io_instance[${ioNo}-1].get_input(${inPinNo}) else False))` + LF); 
    else if (inState === 'off') line_str.push(INDENT + INDENT + INDENT + `L.AND(False if not hasattr(external_io_instance[${ioNo}-1], 'get_input') else (False if external_io_instance[${ioNo}-1].get_input(${inPinNo}) else True))` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   
    // timeout
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `if (hasattr(external_io_instance[${ioNo}-1], 'get_input')):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `pass` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `else:` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    // action
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:This IO No is not defined.', error_yaml=error_yaml)` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    line_str.push(LF);

    
    return line_str.join("");
  };

  python.pythonGenerator.forBlock['set_external_io_output'] = function(block, generator) {
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////   
    const myBlock = self.getBlockAddr(block.customId); 
 

    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const outPinNo = block.getFieldValue('output_pin_name');
    const outState = block.getFieldValue('out_state');
    const ioNo = block.getFieldValue('io_no');

    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + `L.ANB(${self.addr_str}, ${myBlock.myBlock.reset_addr_list[i]})` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    // timeout
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    // action
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `if (hasattr(external_io_instance[${ioNo}-1], 'get_input')):` + LF);
    if      (outState === 'on')  line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `external_io_instance[${ioNo}-1].set_output_on(${outPinNo})` + LF); 
    else if (outState === 'off') line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `external_io_instance[${ioNo}-1].set_output_off(${outPinNo})` + LF); 
    line_str.push(INDENT + INDENT + INDENT + INDENT + `else:` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:This IO No is not defined.', error_yaml=error_yaml)` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    line_str.push(LF);      

    return line_str.join("");
  };

  python.pythonGenerator.forBlock['set_external_io_output_upon'] = function(block, generator) {
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////   
    const myBlock = self.getBlockAddr(block.customId); 
 

    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const condition = generator.valueToCode(block, 'condition', generator.ORDER_ATOMIC) || '0';
    const outPinNo = block.getFieldValue('output_pin_name');
    const outState = block.getFieldValue('out_state');
    const triggerSate = block.getFieldValue('trigger_condition');
    const ioNo = block.getFieldValue('io_no');

    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LD(True if ${condition} else False)` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);   
    // action
    if      (triggerSate === 'steady')  line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    else if (triggerSate === 'rising')  line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    else if (triggerSate === 'falling') line_str.push(INDENT + INDENT + INDENT + `L.LDF(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    if (outState === '100msec')         line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_T['100msec_timer[0]']['name'], L.local_T['100msec_timer[0]']['addr'])` + LF);
    else if (outState === '300msec')    line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_T['300msec_timer[0]']['name'], L.local_T['300msec_timer[0]']['addr'])` + LF);
    else if (outState === '500msec')    line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_T['500msec_timer[0]']['name'], L.local_T['500msec_timer[0]']['addr'])` + LF);
    else if (outState === '1000msec')   line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_T['1000msec_timer[0]']['name'], L.local_T['1000msec_timer[0]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `if (hasattr(external_io_instance[${ioNo}-1], 'get_input')):` + LF);
    if (outState === 'on')        line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `external_io_instance[${ioNo}-1].set_output_on(${outPinNo})` + LF); 
    else if (outState === 'off')  line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `external_io_instance[${ioNo}-1].set_output_off(${outPinNo})` + LF); 
    else{
      line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `external_io_instance[${ioNo}-1].set_output_on(${outPinNo})` + LF); 
      line_str.push(INDENT + INDENT + INDENT + `else:` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `port_index = 0 if(${outPinNo} < 8) else 1` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `pin_no = ${outPinNo} if(${outPinNo} < 8) else (${outPinNo} % 8)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `device_no_offset = (pin_no + (port_index * 8))` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `external_io_instance[${ioNo}-1].set_output_off(${outPinNo}) if (hasattr(external_io_instance[${ioNo}-1], 'get_input')) else None` + LF);
    }
    line_str.push(LF);      

    return line_str.join("");
  };

  python.pythonGenerator.forBlock['set_external_io_output_during'] = function(block, generator) {
    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const ioNo = block.getFieldValue('io_no');
    const outPinNo = block.getFieldValue('output_pin_name');
    const outState = block.getFieldValue('out_state');
    const name = block.getFieldValue('name');
    const timer = `number_param_yaml['${name}']['value']`;
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////    
    const myBlock = self.getBlockAddr(block.customId); 
 
    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_T['block_timer1[${myBlock.index}]']['name'], L.local_T['block_timer1[${myBlock.index}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    // timeout
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    // action
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `if (hasattr(external_io_instance[${ioNo}-1], 'get_input')):` + LF);
    if      (outState === 'on')  line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `external_io_instance[${ioNo}-1].set_output_on(${outPinNo})` + LF); 
    else if (outState === 'off') line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `external_io_instance[${ioNo}-1].set_output_off(${outPinNo})` + LF); 
    line_str.push(INDENT + INDENT + INDENT + INDENT + `else:` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timer1[${myBlock.index}]']['addr'], wait_msec=${timer})` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `if (hasattr(external_io_instance[${ioNo}-1], 'get_input')):` + LF);
    if      (outState === 'on')  line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `external_io_instance[${ioNo}-1].set_output_off(${outPinNo})` + LF); 
    else if (outState === 'off') line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `external_io_instance[${ioNo}-1].set_output_on(${outPinNo})` + LF); 
    line_str.push(INDENT + INDENT + INDENT + INDENT + `else:` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT +`drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:This IO No is not defined.', error_yaml=error_yaml)` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    line_str.push(INDENT + INDENT + LF);

    return line_str.join("");
  };

  python.pythonGenerator.forBlock['set_external_io_output_until'] = function(block, generator) {
    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const ioNo = block.getFieldValue('io_no');
    const outPinNo = block.getFieldValue('output_pin_name');
    const outState = block.getFieldValue('out_state');
    const inPinNo = block.getFieldValue('input_pin_name');
    const inState = block.getFieldValue('in_state');
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////    
    const myBlock = self.getBlockAddr(block.customId); 
 
    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    if      (inState === 'none')  line_str.push(INDENT + INDENT + INDENT + `L.AND(True)` + LF); 
    else if (inState === 'on') line_str.push(INDENT + INDENT + INDENT + `L.AND(False if not hasattr(external_io_instance[${ioNo}-1], 'get_input') else (True if external_io_instance[${ioNo}-1].get_input(${inPinNo}) else False))` + LF); 
    else if (inState === 'off') line_str.push(INDENT + INDENT + INDENT + `L.AND(False if not hasattr(external_io_instance[${ioNo}-1], 'get_input') else (False if external_io_instance[${ioNo}-1].get_input(${inPinNo}) else True))` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    // timeout
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    // action
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `if (hasattr(external_io_instance[${ioNo}-1], 'get_input')):` + LF);
    if      (outState === 'on')  line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `external_io_instance[${ioNo}-1].set_output_on(${outPinNo})` + LF); 
    else if (outState === 'off') line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `external_io_instance[${ioNo}-1].set_output_off(${outPinNo})` + LF); 
    line_str.push(INDENT + INDENT + INDENT + INDENT + `else:` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `if (hasattr(external_io_instance[${ioNo}-1], 'get_input')):` + LF);
    if      (outState === 'on')  line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `external_io_instance[${ioNo}-1].set_output_off(${outPinNo})` + LF); 
    else if (outState === 'off') line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `external_io_instance[${ioNo}-1].set_output_on(${outPinNo})` + LF); 
    line_str.push(INDENT + INDENT + INDENT + INDENT + `else:` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:This IO No is not defined.', error_yaml=error_yaml)` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    line_str.push(LF);

    return line_str.join("");
  };

  python.pythonGenerator.forBlock['external_io'] = function(block, generator) {
    const ioNo = block.getFieldValue('io_no');
    const inPinNo = block.getFieldValue('input_pin_name');
    const code = `(False if not hasattr(external_io_instance[${ioNo}-1], 'get_input') else (True if external_io_instance[${ioNo}-1].get_input(${inPinNo}) else False))`;    
    return [code, generator.ORDER_ATOMIC];
  };

  python.pythonGenerator.forBlock['connect_plc'] = function(block, generator) {
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////   
    const myBlock = self.getBlockAddr(block.customId); 
 

    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const octet1 = block.getFieldValue('octet1');
    const octet2 = block.getFieldValue('octet2');
    const octet3 = block.getFieldValue('octet3');
    const octet4 = block.getFieldValue('octet4');
    const port = block.getFieldValue('port');
    const maker = block.getFieldValue('plc_maker');

    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + `L.ANB(${self.addr_str}, ${myBlock.myBlock.reset_addr_list[i]})` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.AND(plc_connected[0])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    // timeout
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    // action
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT +`L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT +`if (L.aax & L.iix):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `PLC_R_DM = BasePLC()` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `PLC_MR_EM = BasePLC()` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `PLC_R_DM.load_param(dict(ip='${octet1}.${octet2}.${octet3}.${octet4}', port='${port}', manufacturer='${maker}', series='', plc_protocol='slmp', transport_protocol='udp', bit='R', word='DM', double_word=''))` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `PLC_MR_EM.load_param(dict(ip='${octet1}.${octet2}.${octet3}.${octet4}', port='${port}', manufacturer='${maker}', series='', plc_protocol='slmp', transport_protocol='udp', bit='MR', word='EM', double_word=''))` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `plc_instance[0] = {'R_DM': PLC_R_DM, 'MR_EM': PLC_MR_EM}` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `if ((plc_instance[0]['R_DM']) and (plc_instance[0]['MR_EM'])) :` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `plc_connected[0] = True` + LF);
    line_str.push(LF);      
    // error
    line_str.push(INDENT + INDENT + INDENT + `#;error:` + block.customId + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `if (plc_connected[0] == False):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}+0, message=f"${block.customId}:Connection is failed.", error_yaml=error_yaml)` + LF);  
    line_str.push(INDENT + INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}+0, error_yaml=error_yaml)` + LF); 
    line_str.push(LF);      

    return line_str.join("");
  };

  python.pythonGenerator.forBlock['plc_bit'] = function(block, generator) {
    const name = block.getFieldValue('device_name');
    const word_no = block.getFieldValue('device_word_no');
    const bit_no = block.getFieldValue('device_bit_no');
    let code = 'false';
    
    if (name === 'R'){
      code = `True if (hasattr(plc_instance[0]['R_DM'], 'read_data_from_plc')) and (plc_instance[0]['R_DM'].read_data_from_plc(d_type='bit', addr_min='${word_no}${bit_no}', addr_max='${word_no}${bit_no}', multi=True, timeout=1000)[1][0] == 1) else False`;  
    }
    else if(name === 'MR'){
      code = `True if (hasattr(plc_instance[0]['MR_EM'], 'read_data_from_plc')) and (plc_instance[0]['MR_EM'].read_data_from_plc(d_type='bit', addr_min='${word_no}${bit_no}', addr_max='${word_no}${bit_no}', multi=True, timeout=1000)[1][0] == 1) else False`;  
    }
    return [code, generator.ORDER_ATOMIC]; //数値や式として扱う場合は [code, Blockly.Python.ORDER_ATOMIC] を使う
  };

  python.pythonGenerator.forBlock['plc_word'] = function(block, generator) {
    const name = block.getFieldValue('device_name');
    const word_no = block.getFieldValue('device_word_no');
    let code = 'false';
    
    if (name === 'DM'){
      code = `plc_instance[0]['R_DM'].read_data_from_plc(d_type='word', addr_min='${word_no}', addr_max='${word_no}', multi=True, timeout=1000)[1][0] if (hasattr(plc_instance[0]['R_DM'], 'read_data_from_plc')) else -1`;  
    }
    else if(name === 'EM'){
      code = `plc_instance[0]['MR_EM'].read_data_from_plc(d_type='word', addr_min='${word_no}', addr_max='${word_no}', multi=True, timeout=1000)[1][0] if (hasattr(plc_instance[0]['MR_EM'], 'read_data_from_plc')) else -1`;  
    }
    return [code, generator.ORDER_ATOMIC]; //数値や式として扱う場合は [code, Blockly.Python.ORDER_ATOMIC] を使う
  };
  
  python.pythonGenerator.forBlock['set_plc_bit'] = function(block, generator) {  
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////   
    const myBlock = self.getBlockAddr(block.customId); 
 

    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const name = block.getFieldValue('device_name');
    const word_no = block.getFieldValue('device_word_no');
    const bit_no = block.getFieldValue('device_bit_no');
    const state = block.getFieldValue('bit_state');

    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + `L.ANB(${self.addr_str}, ${myBlock.myBlock.reset_addr_list[i]})` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `L.LD(success)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF); 

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    if (name === 'R'){
      line_str.push(INDENT + INDENT + INDENT + INDENT + `success = plc_instance[0]['R_DM'].write_data_to_plc(d_type='bit', addr_min='${word_no}${bit_no}', addr_max='${word_no}${bit_no}', multi=True, data=[1 if('${state}'=='on') else 0], timeout=1000)` + LF);
    }
    else if (name === 'MR'){
      line_str.push(INDENT + INDENT + INDENT + INDENT + `success = plc_instance[0]['MR_EM'].write_data_to_plc(d_type='bit', addr_min='${word_no}${bit_no}', addr_max='${word_no}${bit_no}', multi=True, data=[1 if('${state}'=='on') else 0], timeout=1000)` + LF);
    }
    else {
      line_str.push(INDENT + INDENT + INDENT + INDENT + `pass` + LF);      
    }    
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `success = False` + LF);

    line_str.push(INDENT + INDENT + LF);      

    return line_str.join("");
  };

  python.pythonGenerator.forBlock['set_plc_bit_during'] = function(block, generator) {
    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const name = block.getFieldValue('device_name');
    const word_no = block.getFieldValue('device_word_no');
    const bit_no = block.getFieldValue('device_bit_no');
    const state = block.getFieldValue('bit_state');
    const timer = `number_param_yaml['${block.getFieldValue('number_name')}']['value']`;

    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////    
    const myBlock = self.getBlockAddr(block.customId); 
 

    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + `L.ANB(${self.addr_str}, ${myBlock.myBlock.reset_addr_list[i]})` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_T['block_timer1[${myBlock.index}]']['name'], L.local_T['block_timer1[${myBlock.index}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF); 

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    // ビットON/OFF
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    if (name === 'R'){
      line_str.push(INDENT + INDENT + INDENT + INDENT + `success = plc_instance[0]['R_DM'].write_data_to_plc(d_type='bit', addr_min='${word_no}${bit_no}', addr_max='${word_no}${bit_no}', multi=True, data=[1 if('${state}'=='on') else 0], timeout=1000)` + LF);
    }
    else if (name === 'MR'){
      line_str.push(INDENT + INDENT + INDENT + INDENT + `success = plc_instance[0]['MR_EM'].write_data_to_plc(d_type='bit', addr_min='${word_no}${bit_no}', addr_max='${word_no}${bit_no}', multi=True, data=[1 if('${state}'=='on') else 0], timeout=1000)` + LF);
    }
    else {
      line_str.push(INDENT + INDENT + INDENT + INDENT + `pass` + LF);      
    }    
    // タイマ動作
    line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timer1[${myBlock.index}]']['addr'], wait_msec=${timer})` + LF);
    // ビットOFF/ON
    line_str.push(INDENT + INDENT + INDENT + `L.LDF(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    if (name === 'R'){
      line_str.push(INDENT + INDENT + INDENT + INDENT + `success = plc_instance[0]['R_DM'].write_data_to_plc(d_type='bit', addr_min='${word_no}${bit_no}', addr_max='${word_no}${bit_no}', multi=True, data=[1 if('${state}'=='off') else 0], timeout=1000)` + LF);
    }
    else if (name === 'MR'){
      line_str.push(INDENT + INDENT + INDENT + INDENT + `success = plc_instance[0]['MR_EM'].write_data_to_plc(d_type='bit', addr_min='${word_no}${bit_no}', addr_max='${word_no}${bit_no}', multi=True, data=[1 if('${state}'=='off') else 0], timeout=1000)` + LF);
    }
    else {
      line_str.push(INDENT + INDENT + INDENT + INDENT + `pass` + LF);      
    }    
    line_str.push(INDENT + INDENT + LF);      
    return line_str.join("");

  };

  python.pythonGenerator.forBlock['set_plc_bit_until'] = function(block, generator) {
    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const output_name = block.getFieldValue('output_device_name');
    const output_word_no = block.getFieldValue('output_device_word_no');
    const output_bit_no = block.getFieldValue('output_device_bit_no');
    const output_state = block.getFieldValue('input_bit_state');
    const input_name = block.getFieldValue('input_device_name');
    const input_word_no = block.getFieldValue('input_device_word_no');
    const input_bit_no = block.getFieldValue('input_device_bit_no');
    const input_state = block.getFieldValue('input_bit_state');

    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////    
    const myBlock = self.getBlockAddr(block.customId); 
 

    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + `L.ANB(${self.addr_str}, ${myBlock.myBlock.reset_addr_list[i]})` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    if (input_name === 'R'){
      line_str.push(INDENT + INDENT + INDENT + `L.AND(True if (hasattr(plc_instance[0]['R_DM'], 'read_data_from_plc')) and (plc_instance[0]['R_DM'].read_data_from_plc(d_type='bit', addr_min='${input_word_no}${input_bit_no}', addr_max='${input_word_no}${input_bit_no}', multi=True, timeout=1000)[1][0] == (1 if('${input_state}'=='on') else 0)) else False)` + LF);  
    }
    else if(input_name === 'MR'){
      line_str.push(INDENT + INDENT + INDENT + `L.AND(True if (hasattr(plc_instance[0]['MR_EM'], 'read_data_from_plc')) and (plc_instance[0]['MR_EM'].read_data_from_plc(d_type='bit', addr_min='${input_word_no}${input_bit_no}', addr_max='${input_word_no}${input_bit_no}', multi=True, timeout=1000)[1][0] == (1 if('${input_state}'=='on') else 0)) else False)` + LF);  
    }
    line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF); 

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    // ビットON/OFF
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    if (output_name === 'R'){
      line_str.push(INDENT + INDENT + INDENT + INDENT + `success = plc_instance[0]['R_DM'].write_data_to_plc(d_type='bit', addr_min='${output_word_no}${output_bit_no}', addr_max='${output_word_no}${output_bit_no}', multi=True, data=[1 if('${output_state}'=='on') else 0], timeout=1000)` + LF);
    }
    else if (output_name === 'MR'){
      line_str.push(INDENT + INDENT + INDENT + INDENT + `success = plc_instance[0]['MR_EM'].write_data_to_plc(d_type='bit', addr_min='${output_word_no}${output_bit_no}', addr_max='${output_word_no}${output_bit_no}', multi=True, data=[1 if('${output_state}'=='on') else 0], timeout=1000)` + LF);
    }
    else {
      line_str.push(INDENT + INDENT + INDENT + INDENT + `pass` + LF);      
    }    
    // ビットOFF/ON
    line_str.push(INDENT + INDENT + INDENT + `L.LDF(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    if (output_name === 'R'){
      line_str.push(INDENT + INDENT + INDENT + INDENT + `success = plc_instance[0]['R_DM'].write_data_to_plc(d_type='bit', addr_min='${output_word_no}${output_bit_no}', addr_max='${output_word_no}${output_bit_no}', multi=True, data=[1 if('${output_state}'=='off') else 0], timeout=1000)` + LF);
    }
    else if (output_name === 'MR'){
      line_str.push(INDENT + INDENT + INDENT + INDENT + `success = plc_instance[0]['MR_EM'].write_data_to_plc(d_type='bit', addr_min='${output_word_no}${output_bit_no}', addr_max='${output_word_no}${output_bit_no}', multi=True, data=[1 if('${output_state}'=='off') else 0], timeout=1000)` + LF);
    }
    else {
      line_str.push(INDENT + INDENT + INDENT + INDENT + `pass` + LF);      
    }    
    line_str.push(INDENT + INDENT + LF);      
    return line_str.join("");

  };

  python.pythonGenerator.forBlock['set_plc_word'] = function(block, generator) {  
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////   
    const myBlock = self.getBlockAddr(block.customId); 
 

    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const value = block.getFieldValue('value');
    const name = block.getFieldValue('device_name');
    const word_no = block.getFieldValue('device_word_no');

    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + `L.ANB(${self.addr_str}, ${myBlock.myBlock.reset_addr_list[i]})` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.AND(success)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF); 

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    if (name === 'DM'){
      line_str.push(INDENT + INDENT + INDENT + INDENT + `success = plc_instance[0]['R_DM'].write_data_to_plc(d_type='word', addr_min='${word_no}', addr_max='${word_no}', multi=True, data=[${value}], timeout=1000)` + LF);
    }
    else if (name === 'EM'){
      line_str.push(INDENT + INDENT + INDENT + INDENT + `success = plc_instance[0]['MR_EM'].write_data_to_plc(d_type='word', addr_min='${word_no}', addr_max='${word_no}', multi=True, data=[${value}], timeout=1000)` + LF);
    }
    else {
      line_str.push(INDENT + INDENT + INDENT + INDENT + `pass` + LF);      
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
    line_str.push(INDENT + INDENT + INDENT + INDENT + `success = False` + LF);

    line_str.push(INDENT + INDENT + LF);      

    return line_str.join("");
  };

  // python.pythonGenerator.forBlock['check_pallet'] = function(block, generator) {
  //   // var dropdown_pallet_list = block.getFieldValue('no_list');
  //   // var dropdown_equation_list = block.getFieldValue('equation_list');
  //   // var dropdown_cnt_list = block.getFieldValue('cnt_list');
  //   return '';
  // };

  python.pythonGenerator.forBlock['wait_timer'] = function(block, generator) {
    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    const name = block.getFieldValue('name');
    const timer = `number_param_yaml['${name}']['value']`;

    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////    
    const myBlock = self.getBlockAddr(block.customId); 
 
  
    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.reset_addr_list[i]}]']['addr'])` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_T['block_timer1[${myBlock.index}]']['name'], L.local_T['block_timer1[${myBlock.index}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);   

    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    // timeout
    if (Number(block.timeoutMillis) !== -1){
      line_str.push(INDENT + INDENT + INDENT + `#;timeout:` + block.customId + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timeout[${myBlock.index}]']['addr'], ${block.timeoutMillis})` + LF);
      line_str.push(INDENT + INDENT + INDENT + `L.LDP(L.local_T['block_timeout[${myBlock.index}]']['name'], L.local_T['block_timeout[${myBlock.index}]']['addr'])` + LF);
      line_str.push(INDENT + INDENT + INDENT + `if (L.aax & L.iix):` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.register_error(no=${self.userErrorNo}+${myBlock.index}, message='${block.customId}:A timeout occurred.', error_yaml=error_yaml)` + LF);
      line_str.push(INDENT + INDENT + INDENT + INDENT + `drive.raise_error(no=${self.userErrorNo}+${myBlock.index}, error_yaml=error_yaml)` + LF);
    }
    // action
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.TMS(L.local_T['block_timer1[${myBlock.index}]']['addr'], wait_msec=${timer})` + LF);
    line_str.push(INDENT + INDENT + LF);

    return line_str.join("");
  };
  
  python.pythonGenerator.forBlock['procedures_callnoreturn'] = function(block, generator) {
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////   
    const myBlock = self.getBlockAddr(block.customId); 
    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////

    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      else                               line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + `L.ANB(${self.addr_str}, ${myBlock.myBlock.reset_addr_list[i]})` + LF);
    }
    // if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    // line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.onset_addr}]']['name'], L.local_MR['seq_step[${myBlock.onset_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.onset_addr}]']['name'], L.local_MR['seq_step[${myBlock.onset_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    // action
    line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // Prev.ボタン対応
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] !== 992002){
        if (i === 0){
          line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.def_func_start_addr}]']['name'], L.local_MR['seq_step[${myBlock.def_func_start_addr}]']['addr'])` + LF);
        }
        else{
          line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        }
        line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
      }
    }
    line_str.push(LF);              

    return line_str.join("");
  };

  python.pythonGenerator.forBlock['procedures_defnoreturn'] = function(block, generator) {
    //////////////////////////////////////////////////
    // アドレス参照
    //////////////////////////////////////////////////   
    const myBlock = self.getBlockAddr(block.customId); 
    //////////////////////////////////////////////////
    // 前処理
    //////////////////////////////////////////////////
    //////////////////////////////////////////////////
    // プロセス
    //////////////////////////////////////////////////
    let LF = '\n';
    let INDENT = '  ';
    let line_str = [];
    line_str.push(INDENT + INDENT + INDENT + `#;Process:` + block.customId + LF);
    for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
      if(myBlock.survival1_addr_list[i] === 992002) {
        line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_R['program_start[0]']['name'], L.local_R['program_start[0]']['addr'])` + LF);
      }
      else{
        if (i === 0) line_str.push(INDENT + INDENT + INDENT + `L.LD(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
        else line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
      }
    }
    if(myBlock.reset_addr_list){
      for (let i = 0; i < myBlock.reset_addr_list.length; i++) line_str.push(INDENT + INDENT + `L.ANB(${self.addr_str}, ${myBlock.myBlock.reset_addr_list[i]})` + LF);
    }
    if (myBlock.index !== -1) line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step_reset1[${myBlock.index}]']['name'], L.local_MR['seq_step_reset1[${myBlock.index}]']['addr'])` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.MPS()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANB(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.MPP()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDB(MR, 304)` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANPB(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7801)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ORB(R, 7800)` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF); 
    line_str.push(INDENT + INDENT + INDENT + `L.OR(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.ANL()` + LF);
    line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step[${myBlock.stop1_addr}]']['name'], L.local_MR['seq_step[${myBlock.stop1_addr}]']['addr'])` + LF);
    //////////////////////////////////////////////////
    // プロセス後動作
    //////////////////////////////////////////////////
    line_str.push(INDENT + INDENT + INDENT + `#;Post-Process:` + block.customId + LF);
    // action
    // line_str.push(INDENT + INDENT + INDENT + `#;action:` + block.customId + LF);
    // // Prev.ボタン対応
    // for (let i = 0; i < myBlock.survival1_addr_list.length; i++) {
    //   if(myBlock.survival1_addr_list[i] !== 992002){
    //     if (i === 0){
    //       line_str.push(INDENT + INDENT + INDENT + `L.LDP(R, 7802)` + LF);
    //       line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.start_addr}]']['name'], L.local_MR['seq_step[${myBlock.start_addr}]']['addr'])` + LF);
    //     }
    //     else{
    //       line_str.push(INDENT + INDENT + INDENT + `L.AND(L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['name'], L.local_MR['seq_step[${myBlock.survival1_addr_list[i]}]']['addr'])` + LF);
    //     }
    //     line_str.push(INDENT + INDENT + INDENT + `L.OUT(L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['name'], L.local_MR['seq_step_reset${myBlock.prev_branch_num}[${myBlock.prev_index}]']['addr'])` + LF);
    //   }
    // }
    line_str.push(LF);              
    //////////////////////////////////////////////////
    // 後処理
    //////////////////////////////////////////////////
    const innerBlock = block.getInputTargetBlock('STACK');
    let innerCode = '';
    if (innerBlock) {
      // 内包ブロックからPythonコードを生成
      innerCode = python.pythonGenerator.blockToCode(innerBlock);
    }


    return line_str.join("") + innerCode;
  };

  };
}

export { BlockUtility, BlockFlow, BlockForm, BlockCode};