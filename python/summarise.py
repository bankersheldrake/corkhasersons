    async def fnPullAdminEvents(self,ptRequest:dict) -> APIResponse:
        print("Called fnPullAdminEvents")
        """Return the events which are saved to the db for a given filter criteria

        Parameters
        ----------
        ptRequest : dict
            # ptRequest['tSession']['userid']
            # ptRequest['request.json']
            # ptRequest['sSessionProgressID']
            ptRequest['request.headers']  -- looking for total row count

        Returns
        -------
            {   data:{}
                error:{}
                finalstate:{}
            }

        """
        tPushMessage={}
        bPopulatingTemp:bool=False
        bReloadTempData=None

        async def _fnSetAdminEventsStatus(ptRequest: str, ptParams: dict, opbRaiseError: bool = False) -> dict:
            # set the shared adminevents session
            print(f"Called for {ptParams}")
            # push notification to the client
            await self.fnQueuePushMessage('',ptRequest['tSession']['sessionid'],{'eventname':'datatable.dataupdate'
                                                                                 ,'data':{'other':fnGetDictIndex(ptParams,'otherprogress')}})
            # tReturn = self.fnSetProgress(psProgressID=f"{ptRequest['tSession']['sessionid']}.PAE"
            #                                     ,ptParams={'checkexists':fnGetDictIndex(ptParams,'checkexists',None,False)
            #                                         ,'getprogress':fnGetDictIndex(ptParams,'getprogress',None,False)
            #                                         ,'percentage':fnGetDictIndex(ptParams,'percentage')
            #                                         ,'errorlevel':fnGetDictIndex(ptParams,'errorlevel')
            #                                         ,'otherprogress':fnGetDictIndex(ptParams,'otherprogress')
            #                                         ,'neverclosed':True}
            #                                     )
            # update the client progresssession
            if ptRequest['sSessionProgressID']:
                self.fnSetProgress(psProgressID=ptRequest['sSessionProgressID']
                                                ,ptParams={'checkexists':fnGetDictIndex(ptParams,'checkexists')
                                                    ,'percentage':fnGetDictIndex(ptParams,'percentage')
                                                    ,'status':fnGetDictIndex(ptParams,'status')
                                                    ,'tooltip':fnGetDictIndex(ptParams,'tooltip')
                                                    ,'errorlevel':fnGetDictIndex(ptParams,'errorlevel')
                                                    }
                                                )
            if fnGetDictIndex(ptParams,'getprogress',None,False):
                return tReturn
            
        def _fnCheckSessionState(ptSessionState: Dict[str, Union[str, bool, Dict[str, Union[str, bool]]]],psContext:str,pbCheckContinue:bool):
            nonlocal bPopulatingTemp
            bContinue=True
            # print('in',bContinue,bPopulatingTemp)
            # if fnGetDictIndex(ptSessionState, 'error'):
            #     print(f"{psContext} - Session cancelled: {fnGetDictIndex(ptSessionState, 'error')}")
            #     bContinue=False
            # elif pbCheckContinue and not fnGetDictIndex(ptSessionState, 'continue'):
            #     print(f"{psContext} - Session cant continue: {fnGetDictIndex(ptSessionState, 'reason')}")
            #     bContinue = False
            # elif fnGetDictIndex(ptSessionState, 'final') or fnGetDictIndex(ptSessionState, 'complete'):
            #     print(f"{psContext} - Session finished")
            #     bContinue = False
            # elif fnGetDictIndex(ptSessionState, 'progress.other.cancelinsert'):
            #     print(f"{psContext} - Insert cancelled by user")
            #     bContinue = False
            # elif fnGetDictIndex(ptSessionState, 'progress.other.insertfinished'):
            #     print(f"{psContext} - Insert finished")
            #     bContinue = False
            # if not bContinue:
            #     bPopulatingTemp=False
            # print('out',bContinue,bPopulatingTemp)
            return bContinue
        # ptSessionState = {'error':'here','final':{},'continue':False,'reason':'fdsafdsafds','progress':{'other':{'cancelinsert':True,'insertfinished':True}}}
        bEventID=False
        bDataSearch=False
        tSpecificTranslate:dict={}
        sError=''
        tCookieFunctions=[]
        print(f"PullAdminEvents: {ptRequest}")
        while True:
            try:
                print('fnPullAdminEvents',ptRequest['request.json'])
                # await fnAsyncSleep(5)
                def _fnBuildSearch(ptRequest:dict)->dict:
                    tOut= {'sourcetype':fnGetDictIndex(ptRequest['request.json'],'searchparams.sourcetable')}
                    if tOut['sourcetype']=='sensordata':
                        # new newmedia
                        tOut['event_date_col'] = 'd_l_SystemLogging.eventdate'
                        tOut['event_type_col'] = 's_t_SystemLogTypes.name'
                        tOut['event_outcome_col'] = 'd_l_SystemLogging.attributes'
                        tOut['json_search_col'] = 'd_l_SystemLogging.attributes'
                        tOut['primary_key_col'] = 'd_l_SystemLogging.eventid'
                        tOut['events_table_name'] = '(SELECT * FROM d_l_SystemLogging LIMIT 5000) d_l_SystemLogging'
                        tOut['table_join'] = ' LEFT OUTER JOIN s_t_SystemLogTypes ON d_l_SystemLogging.eventtypeid = s_t_SystemLogTypes.eventtypeid ' #LEFT OUTER JOIN d_q_tableindexactions ON d_q_tableindexactions.queuetypeid = 1 AND d_q_tableindexactions.indexid = d_l_SystemLogging.eventid
                        tOut['user_savedsearch_prefname'] = 'sputnikadmin.events'
                        tOut['database_name'] = 'SensorData'
                        tOut['default_where'] = ' WHERE d_l_SystemLogging.flag = 0 '
                    elif tOut['sourcetype']=='adminevents':
                        tOut['event_date_col'] = 'd_l_AdminEvents.eventdate'
                        tOut['event_type_col'] = 'd_l_AdminEvents.eventattributes_function'
                        tOut['event_typeid_col'] = 'd_l_AdminEvents.admineventtypeid'
                        tOut['event_outcome_col'] = 'd_l_AdminEvents.eventattributes_outcome_complete'
                        tOut['json_search_col'] = 'd_l_AdminEvents.eventattributes'
                        tOut['primary_key_col'] = 'd_l_AdminEvents.admineventid'
                        tOut['events_table_name'] = '(SELECT * FROM d_l_AdminEvents LIMIT 5000) d_l_AdminEvents'
                        tOut['table_join'] = ''
                        tOut['default_where'] = ' WHERE 1 '
                        tOut['user_savedsearch_prefname'] = 'kodiakadmin'
                        tOut['database_name'] = 'Media'
                        tOut['sourcetype'] = 'adminevents'

                    else:
                        tOut['sError'] = f"Unrecognised sourcetable: {tOut['sourcetype']}"
                    tblVars = dict()
                    tInnerSearchVars = {'length':10}
                    if fnIfDictHasIndex(ptRequest['request.json'],'searchparams.eventtypeid'):
                        tInnerSearchVars['eventtypeid'] = ptRequest['request.json']['searchparams']['eventtypeid']
                    tblVars['datewhere'] = ''
                    if 'dt_search_start' in ptRequest['request.json']['searchparams']:
                        tblVars['datewhere'] = tblVars['datewhere'] + f" AND {tOut['event_date_col']} >= %(dt_search_start)s "
                        tInnerSearchVars['dt_search_start'] = datetime.datetime.strptime(ptRequest['request.json']['searchparams']['dt_search_start'], "%Y-%m-%dT%H:%M:%S.%f%z")
                        # datetime.datetime.fromisoformat(ptRequest['request.json']['searchparams']['dt_search_start'])
                    if 'dt_search_end' in ptRequest['request.json']['searchparams']:
                        tblVars['datewhere'] = tblVars['datewhere'] + f" AND {tOut['event_date_col']} < %(dt_search_end)s "

                        # print(datetime.datetime.strptime(ptRequest['request.json']['searchparams']['dt_search_end'], "%Y-%m-%dT%H:%M:%S.%f%z"))

                        tInnerSearchVars['dt_search_end'] = datetime.datetime.strptime(ptRequest['request.json']['searchparams']['dt_search_end'], "%Y-%m-%dT%H:%M:%S.%f%z")

                    tblVars['eventtypewhere'] = ''
                    bInclude = False
                    if 'select_events_filter' in ptRequest['request.json']['searchparams']:
                        lTagNumb:int = 1

                        for tTag in ptRequest['request.json']['searchparams']['select_events_filter']:
                            bInclude=True
                            tblVars['eventtypewhere'] += f"%(tag{lTagNumb}_key)s,"
                            tInnerSearchVars[f"tag{lTagNumb}_key"] = tTag
                            lTagNumb += 1
                        if bInclude:
                            # print(tblVars['eventtypewhere'][:-5])
                            tblVars['eventtypewhere'] = f" AND {tOut['event_type_col']} IN ({tblVars['eventtypewhere']}null) "
                    if fnIfDictHasIndex(tInnerSearchVars,'eventtypeid'):
                        sInnerSQLWhere = f" {tOut['default_where']} AND {tOut['event_typeid_col']} = %(eventtypeid)s"
                    else:
                        sInnerSQLWhere = tOut['default_where']
                    for sVarType in tblVars:
                        # print(sVarType)
                        if len(tblVars[sVarType]) > 0:
                            sInnerSQLWhere += tblVars[sVarType]


                    # Window and row count
                    if fnIfDictHasIndex(ptRequest['request.json'], 'dtparams.start'):
                        tInnerSearchVars['length'] = ptRequest['request.json']['dtparams']['length']
                        tInnerSearchVars['start'] = ptRequest['request.json']['dtparams']['start']
                        sInnerSQLLimit = " %(start)s,%(length)s;"
                    else:
                        sInnerSQLLimit = " %(length)s;"

                    # JSON search
                    if fnGetDictIndex(ptRequest['request.json'], 'dtparams.search.value','',None):

                        if fnGetDictIndex(ptRequest['request.json'], 'dtparams.search.regex'):
                            print('regex not supported')
                        sInnerSQLWhere = f"{sInnerSQLWhere} AND JSON_SEARCH({tOut['json_search_col']}, 'one', %(dtsearch)s, NULL, %(dtsearchjsonkey)s) IS NOT NULL"
                        tJSONKeys = ptRequest['request.json']['dtparams']['search']['value'].split('=')
                        if len(tJSONKeys)==2:
                            tInnerSearchVars['dtsearchjsonkey'] = tJSONKeys[0]
                            tInnerSearchVars['dtsearch'] = tJSONKeys[1]
                        else:
                            tInnerSearchVars['dtsearch'] = ptRequest['request.json']['dtparams']['search']['value']
                            tInnerSearchVars['dtsearchjsonkey']='$'
                        fnSetDictIndex(ptRequest['request.json']['searchparams'],'dtparams.search',fnGetDictIndex(ptRequest['request.json'], 'dtparams.search'))

                    # process datatable settings
                    tOrderBy = fnGetDictIndex(ptRequest['request.json'], 'dtparams.order')

                    sInnerSQLOrderBy = f"{tOut['primary_key_col']} DESC"

                    # print(ptRequest['request.json']['dtparams'])
                    # print(ptRequest['request.json']['dtparams']['columns'])
                    lColCount=-1
                    bExists=False
                    if fnIfDictHasIndex(ptRequest['request.json'], 'dtparams.columns'):
                        for tCol in ptRequest['request.json']['dtparams']['columns']:
                            lColCount+=1
                            bSearch=False
                            sOrderDir=''
                            sColName=''
                            # print(tCol)
                            if fnGetDictIndex(tCol, 'search.value','',None):
                                if fnGetDictIndex(tCol, 'search.regex'):
                                    print('regex not supported')
                                # print(f"Search by {tCol['name']}")
                                bSearch = True
                            for tOrder in tOrderBy:
                                lDTOrderBy = fnGetDictIndex(tOrder, 'column')
                                if lDTOrderBy==lColCount:
                                    # print(f"Order by {tCol['name']}")
                                    sOrderDir=fnGetDictIndex(tOrder, 'dir')
                                # Orderby this column
                            if bSearch or sOrderDir:
                                if tCol['name'] == 'eventid':
                                    sColName = f"{tOut['primary_key_col']}"
                                elif tCol['name'] == 'event':
                                    sColName = f"{tOut['event_type_col']}"
                                elif tCol['name'] == 'date':
                                    sColName = f"DATE_FORMAT({tOut['event_date_col']}, '%%Y-%%m-%%d %%T')"
                                elif tCol['name'] == 'outcome':
                                    sColName = f"{tOut['event_outcome_col']}"
                                else:
                                    print(f"Definition is wrong, {tCol['name']} not recognised in this dataset. bSearch: {bSearch} sOrderDir: {sOrderDir}")
                                    bSearch=False
                                    sOrderDir=''
                            if bSearch:
                                sInnerSQLWhere = sInnerSQLWhere + f" AND {sColName} LIKE %(dtsearch.{tCol['data']})s"
                                tInnerSearchVars[f"dtsearch.{tCol['data']}"] = '%' + tCol['search']['value'] + '%'
                                bExists=True
                            if sOrderDir:
                                sInnerSQLOrderBy = f"{sColName} {sOrderDir},{sInnerSQLOrderBy}"
                                bExists=True

                        if bExists:
                            fnSetDictIndex(ptRequest['request.json']['searchparams'],'dtparams.columns',fnGetDictIndex(ptRequest['request.json'], 'dtparams.columns'))

                    tOut['tSearchVars']=tInnerSearchVars
                    tOut['sSQLWhere']=sInnerSQLWhere
                    tOut['sSQLOrderBy']=sInnerSQLOrderBy
                    tOut['sSQLLimit']=sInnerSQLLimit

                    return tOut

                async def _fnPullEventIDsToTempDB(lFoundFileTable:int,pbGetTableRowCount:bool,psSessionProgressID:str,ptTranslations:dict):
                    try:
                        if not pbGetTableRowCount:
                            tSessionState = self.fnGetProgress(psProgressID=psSessionProgressID)
                            if not fnIfDictHasIndex(tSessionState, 'progress.other.recordsTotal'):
                                pbGetTableRowCount=True
                        # lFoundFileTable=0
                        if pbGetTableRowCount:
                            dtStart = time.time()
                            # print("Reload as inital draw")
                            # SELECT 1 FROM d_l_SystemLogging WHERE d_l_SystemLogging.flag != 0 LIMIT 1
                            sSQLStatement = f"""SELECT COUNT(*)
                                    FROM {ptTranslations['events_table_name']}
                                    {ptTranslations['default_where']}
                                    """
                            # print(sSQLStatement)
                            tDataRows = await self.fnPullRecords(ptRequest['sSessionProgressID'],sSQLStatement,{},ptTranslations['database_name'])
                            # print(tDataRows)
                            lRowCount = tDataRows[0][0]
                            print(f"Time to calculate Total row count = {lRowCount}; {time.time()-dtStart}")
                            # self.fnSetProgress(psProgressID=ptRequest['sSessionProgressID']
                            #                     ,ptParams={'percentage':-1
                            #                         ,'status':'Calculated row count'
                            #                         ,'errorlevel':0
                            #                         ,'otherprogress':{'recordsTotal':lRowCount}})
                            await _fnSetAdminEventsStatus(ptRequest=ptRequest
                                                ,ptParams={'percentage':-1
                                                    ,'status':'Calculated row count'
                                                    ,'errorlevel':0
                                                    ,'otherprogress':{'recordsTotal':lRowCount}})
                        # self.fnSetProgress(psProgressID=ptRequest['sSessionProgressID'],ptParams={'percentage':-1,'status':'calculate table row count'})
                        dtStart = time.time()
                        print(f"Starting full temp table insert")
                        # lFoundFileTable:int = await self._oKodiakShared.fnDBTemp_CreateNewTable(pbIndexIntVal=True,psDatabase=ptTranslations['database_name'])
                        # return await self._oKodiakShared.fnDBTemp_CreateNewTable(pbIndexIntVal=pbIndexIntVal,pbIndexKeyVal=pbIndexKeyVal,psDatabase=psDatabase)
                        await _fnSetAdminEventsStatus(ptRequest=ptRequest
                                            ,ptParams={'percentage':-1
                                                ,'status':'Starting full temp insert'
                                                ,'errorlevel':0
                                                ,'otherprogress':{'cancelinsert':False,'insertfinished':False}})
                        sSQLStatement = f"""INSERT INTO [TEMPTABLENAME] (intval)
                            SELECT {ptTranslations['primary_key_col']}
                            FROM {ptTranslations['events_table_name']}{ptTranslations['table_join']}
                            {sSQLWhere}
                            ORDER BY {sSQLOrderBy}
                            LIMIT %(insert_start)s,%(insert_length)s;"""
                        # print(f"The loop {sSQLStatement}")

                        ptTranslations['tSearchVars']['insert_start'] = ptTranslations['tSearchVars']['length']
                        ptTranslations['tSearchVars']['insert_length'] = 10
                        lFilteredRowCount=0
                        # print('here')
                        # try:
                        #     oProgress = self.oCLIProgress(ProgType.FillingSquaresBar,{'caption':'Loading','suffix':'%(percent)d%%','max':20})
                        #     print('fdsfdsafdsfdsa')
                        #     print(oProgress)
                        # except Exception as eError:
                        #     poShared.fnTracePrint(f"there", eError,True)
                        while True:

                            # print(f"Insert in {ptTranslations['tSearchVars']['insert_start']}")
                            # await fnAsyncSleep(0.1)
                            tRowCount = await self._oKodiakShared.fnDBTemp_Exec(lFoundFileTable,sSQLStatement,ptTranslations['tSearchVars'],{'rowcount':True})
                            try:
                                tSessionState = await _fnSetAdminEventsStatus(ptRequest=ptRequest
                                                ,ptParams={'checkexists':True
                                                    ,'getprogress':True
                                                    ,'percentage':-1
                                                    ,'status':'populating table data'
                                                    ,'tooltip':f"rowcount {lFilteredRowCount}"
                                                    ,'errorlevel':0
                                                    ,'otherprogress':{"recordsFiltered":lFilteredRowCount,'dontrefresh':True}}
                                                )

                                # print('nextspinner')
                                # oProgress.next()
                                # print('nextspinner out')
                                print('*')
                                lFilteredRowCount = int(ptTranslations['tSearchVars']['insert_start'])+int(tRowCount['rowcount'])
                                if int(tRowCount['rowcount']) < int(ptTranslations['tSearchVars']['insert_length']):
                                    print(f"Exit loop and no more rows = {lFilteredRowCount}")
                                    break
                                if not _fnCheckSessionState(tSessionState,'Bulk',True):
                                    print('Session is dead')
                                    break

                                ptTranslations['tSearchVars']['insert_start']+=ptTranslations['tSearchVars']['insert_length']
                                if fnGetDictIndex(tSessionState, 'progress.other.finishinbulk'):
                                    print(f"told to complete insert in bulk")
                                    ptTranslations['tSearchVars']['insert_length']=10000000000  #10billion
                                if fnGetDictIndex(tSessionState, 'progress.other.clientwaiting',None,0)!=0:
                                    # Tell the client to go
                                    await _fnSetAdminEventsStatus(ptRequest=ptRequest
                                                       ,ptParams={'percentage':-1,'otherprogress':{"clientwaiting":1}})
                                    while True:

                                        try:
                                            print(f"There is a client knocking {ptRequest['sSessionProgressID']}; {tSessionState}; {fnGetDictIndex(tSessionState, 'progress.other.clientwaiting')}")
                                            await fnAsyncSleep(1)
                                            # print(f"\r")
                                            tSessionState = self.fnGetProgress(psProgressID=ptRequest['sSessionProgressID'])
                                            if not _fnCheckSessionState(tSessionState,'Bulk Wait Client',False):
                                                print(f"Session has been stopped/cancelled/killed, allow temp insert to continu")
                                                break
                                            if not fnGetDictIndex(tSessionState, 'progress.other.clientwaiting') in [1]:
                                                print(f"The client has finished, allow temp insert to continue")
                                                await _fnSetAdminEventsStatus(ptRequest=ptRequest
                                                            ,ptParams={'percentage':-1
                                                                ,'status':'The client has finished, allow temp insert to continue'
                                                                ,'otherprogress':{"clientwaiting":1}
                                                                }
                                                            )
                                                break
                                        except Exception as eError:
                                            print(fnPrintError(f"Error waiting for client to finish", eError,True))
                                            break

                                    # print(f"Client has finished, or session closed")
                                    await _fnSetAdminEventsStatus(ptRequest=ptRequest,ptParams={
                                            'percentage':-1
                                            ,'status':'querying database'
                                            ,'otherprogress':{"clientwaiting":0,"recordsFiltered":lFilteredRowCount,"dontrefresh":True}})

                            except Exception as eError:
                                fnPrintError(f"", eError,True)
                                print('Exit due to error')
                                break

                        # print(f"Out of loop row count = {lFilteredRowCount}")
                        await _fnSetAdminEventsStatus(ptRequest=ptRequest,ptParams={'percentage':100
                            ,'status':'finished'
                            ,'tooltip':f"rowcount {lFilteredRowCount}"
                            ,'errorlevel':0
                            ,'otherprogress':{"clientwaiting":1,"insertfinished":True,"recordsFiltered":lFilteredRowCount}})
                    except Exception as eError:
                        print(fnPrintError("",eError,True))
                    print(f"Time to finish {ptTranslations['events_table_name']} full temp insert {time.time()-dtStart}")
                # END of asyn fn


                tSpecificTranslate = _fnBuildSearch(ptRequest)

                if fnIfDictHasIndex(tSpecificTranslate,'sError'):
                    sError=tSpecificTranslate['sError']
                    break

                if fnGetDictIndex(ptRequest['request.json'],'eventid'):
                    sStatement = f"SELECT {tSpecificTranslate['primary_key_col']},{tSpecificTranslate['json_search_col']} FROM {tSpecificTranslate['events_table_name']}{tSpecificTranslate['table_join']} WHERE {tSpecificTranslate['primary_key_col']} = %(eventid)s;"
                    tSearchVars = {'eventid':ptRequest['request.json']['eventid']}
                    await _fnSetAdminEventsStatus(ptRequest=ptRequest,ptParams={'percentage':-1,'status':'pull eventid'})
                    tDataRows = await self.fnPullRecords(ptRequest['sSessionProgressID'],sStatement,tSearchVars,tSpecificTranslate['database_name'])
                    tDataReturn = {"data":tDataRows
                          }
                    break

                print(f"Is there a progressid for this call? {ptRequest['sSessionProgressID']}")
                if not self.fnValidateSession(psProgressID=ptRequest['sSessionProgressID']):
                    # create a session
                    tSessionState = await _fnSetAdminEventsStatus(ptRequest=ptRequest
                                        ,ptParams={'percentage':-1
                                            ,'status':'Commencing new pull events session'
                                            ,'errorlevel':0
                                            ,'otherprogress':{'cancelinsert':False,'insertfinished':False}}
                                        )            
                else:
                    tSessionState = self.fnGetProgress(psProgressID=ptRequest['sSessionProgressID'])
                    print(f"Getting the session state on first call {tSessionState}")
                    if not fnIfDictHasIndex(tSessionState,'error'):
                        # New session
                        lOrderByHash = fnGetDictIndex(tSessionState, 'progress.other.orderbyhash')

                        # Is it finished but needs to be updated?
                        if not lOrderByHash:
                            print(f"Existing session is not a temp import: tSessionState: {tSessionState}; tSpecificTranslate: {tSpecificTranslate}")
                            print(str(fnGetDictIndex(ptRequest['tSession'],f"{tSpecificTranslate['sourcetype']}-dt-rows",None,'')) + " != " + str(fnGetDictIndex(ptRequest['request.json'],'tempdtrowcount',None,'')))
                            print(str(fnGetDictIndex(ptRequest['tSession'],f"{tSpecificTranslate['sourcetype']}-dt-filteredrows",None,'')) + " != " + str(fnGetDictIndex(ptRequest['request.json'],'tempdtfilteredrowcount',None,'')))
                        elif fnGetDictIndex(tSessionState, 'progress.other.insertfinished'):
                            print(f"Insert finished - {tSessionState}")
                            bPopulatingTemp=False
                        else:
                            print(f"Already running - {tSessionState}")
                            bPopulatingTemp=True
                            lTempRowCount = fnGetDictIndex(tSessionState, 'progress.other.recordsFiltered')
                    else:
                        print(f"PullAdminEvents: Session error {ptRequest['sSessionProgressID']}: {tSessionState}")

                if not bPopulatingTemp:
                    # print(f"{ptRequest['tSession'][f"{tSpecificTranslate['sourcetype']}-dt-filteredrows"]} ?== {fnGetDictIndex(ptRequest['request.json'],'tempdtfilteredrowcount')}")
                    # print(str(fnGetDictIndex(ptRequest['tSession'],f"{tSpecificTranslate['sourcetype']}-dt-rows",None,'')) + "?==" + str(fnGetDictIndex(ptRequest['request.json'],'tempdtrowcount',None,'')))
                    # print(str(fnGetDictIndex(ptRequest['tSession'],f"{tSpecificTranslate['sourcetype']}-dt-filteredrows",None,'')) + "?==" + str(fnGetDictIndex(ptRequest['request.json'],'tempdtfilteredrowcount',None,'')))
                    # print(f"{ptRequest['request.json']}")
                    # print('tryiut')
                    # oProgress = self.oCLIProgress(ProgType.FillingSquaresBar,{'caption':'Loading','suffix':'%(percent)d%%','max':20})
                    # while True:
                    #     await fnAsyncSleep(0.5)
                    #     oProgress.next()
                    if fnGetDictIndex(ptRequest['request.json'],'tempdtrowcount') and fnGetDictIndex(ptRequest['tSession'],f"{tSpecificTranslate['sourcetype']}-dt-rows",None,'') != fnGetDictIndex(ptRequest['request.json'],'tempdtrowcount',None,''):
                        bFirstRun=True
                        lRowCount=fnGetDictIndex(ptRequest['request.json'],'tempdtrowcount')
                        ptRequest['tSession'][f"{tSpecificTranslate['sourcetype']}-dt-rows"]=lRowCount
                    # else:
                    #     lRowCount = fnGetDictIndex(ptRequest['tSession'],f"{tSpecificTranslate['sourcetype']}-dt-rows")

                    if fnGetDictIndex(ptRequest['request.json'],'tempdtfilteredrowcount') and fnGetDictIndex(ptRequest['tSession'],f"{tSpecificTranslate['sourcetype']}-dt-filteredrows",None,'') != fnGetDictIndex(ptRequest['request.json'],'tempdtfilteredrowcount',None,''):
                        bFirstRun=True
                        lFilteredRowCount=fnGetDictIndex(ptRequest['request.json'],'tempdtfilteredrowcount')
                        ptRequest['tSession'][f"{tSpecificTranslate['sourcetype']}-dt-filteredrows"]=lFilteredRowCount
                    # else:
                    #     lTempRowCount = fnGetDictIndex(ptRequest['tSession'],f"{tSpecificTranslate['sourcetype']}-dt-filteredrows")

                sSQLWhere=tSpecificTranslate['sSQLWhere']
                sSQLOrderBy=tSpecificTranslate['sSQLOrderBy']
                sSQLLimit=tSpecificTranslate['sSQLLimit']
                tSearchVars=tSpecificTranslate['tSearchVars']
                # print(f"Insert out {lFilteredRowCount}; psSessionProgressID: {psSessionProgressID}; tSessionState:{tSessionState}")


                bFirstRun=False

                if fnGetDictIndex(ptRequest['request.json'],'searchparams.archiveevents'):
                    if bPopulatingTemp:
                        print('Waiting for tempdb insert to finish before we can start the archive')
                        tSessionState = await _fnSetAdminEventsStatus(ptRequest=ptRequest,ptParams={'checkexists':True,'otherprogress':{"finishinbulk":True}})
                        if _fnCheckSessionState(tSessionState,'Archive',True):
                            while True:
                                print('Waiting for tempdb insert to finish, archive')
                                await fnAsyncSleep(1)
                                tSessionState = self.fnGetProgress(psProgressID=ptRequest['sSessionProgressID'])
                                if not _fnCheckSessionState(tSessionState,'Archive',False):
                                    break
                                # print(f"Insert out {lFilteredRowCount}; tSessionState:{tSessionState}")

                    await _fnSetAdminEventsStatus(ptRequest=ptRequest,ptParams={'percentage':-1,'status':'set archive flag'})
                    lTotalRows = ptRequest['tSession'][f"{tSpecificTranslate['sourcetype']}-dt-filteredrows"]
                    lFilteredRowCount = 0
                    lRowsPerLoop = 100
                    dtStart = time.time()
                    print(f"Counts before loop bPopulatingTemp: {bPopulatingTemp}; lTotalRows: {lTotalRows}")
                    while True:

                        tSessionState = await _fnSetAdminEventsStatus(ptRequest=ptRequest
                                            ,ptParams={'checkexists':True
                                                       ,'percentage':10 + (90*float(lFilteredRowCount)/float(lTotalRows))
                                                       ,'status':'Flagging Records'})
                        if fnGetDictIndex(tSessionState,'continue'):
                            # print(f"do the update {lFilteredRowCount}")
                            lFoundFileTable = ptRequest['tSession'][f"{tSpecificTranslate['sourcetype']}-dt-temptableid"]
                            tRowCount = await self._oKodiakShared.fnDBTemp_Exec(lFoundFileTable, f"""UPDATE {tSpecificTranslate['events_table_name']}{tSpecificTranslate['table_join']}
                                    INNER JOIN [TEMPTABLENAME] ON {tSpecificTranslate['primary_key_col']} = [TEMPTABLENAME].intval AND d_l_SystemLogging.flag = 0
                                    SET d_l_SystemLogging.flag = 1
                                    LIMIT {lRowsPerLoop};
                                    """,tSearchVars,{'rowcount':True})
                            lFilteredRowCount+=lRowsPerLoop
                            # print(tRowCount)
                            if fnGetDictIndex(tRowCount,'rowcount')!=lRowsPerLoop:
                                break
                        else:
                            # Cancel
                            print(f"Update cancelled {fnGetDictIndex(tSessionState,'reason')}")
                            break
                    print(f"Time to finish {tSpecificTranslate['events_table_name']} archive log {time.time()-dtStart}")
                    tDataReturn = {"data":"Flagged " + str(lTotalRows) + " rows for archive "}
                    break

                sSearchHash=sSQLWhere
                for sTag in tSearchVars:
                    sSearchHash=sSearchHash.replace(f"%({sTag})s",str(tSearchVars[sTag]))

                sSearchHash = hash(sSearchHash)
                bReloadTempData=None
                lRowCount = fnGetDictIndex(ptRequest['tSession'],f"{tSpecificTranslate['sourcetype']}-dt-rows")
                if not lRowCount: #fnGetDictIndex(ptRequest['request.json'],'dtparams.draw')==1 or
                    print(f"Reload True as not lRowCount")
                    # Need to refresh the temp table, get the first n rows, and push the temp table population out
                    bReloadTempData=True
                elif sSearchHash != fnGetDictIndex(ptRequest['tSession'],f"{tSpecificTranslate['sourcetype']}-dt-filterhash"):
                    print(f"Reload False as {sSearchHash} != " + str(fnGetDictIndex(ptRequest['tSession'],f"{tSpecificTranslate['sourcetype']}-dt-filterhash")))
                    bReloadTempData=False
                else:
                    print(f"lRowCount: {lRowCount} and sSearchHash hasnt changed: {sSearchHash} == " + str(fnGetDictIndex(ptRequest['tSession'],f"{tSpecificTranslate['sourcetype']}-dt-filterhash")))
                    print(f"This means that we can reuse the existing temp table of data")
                    # print("--------------------NORMALLY WE LET TEMP CARRY ON---------------")
                    # bReloadTempData=False

                if bReloadTempData==True or bReloadTempData==False:
                    if bPopulatingTemp:
                        print(f"Waiting for tempdb insert to finish, it must be killed {bReloadTempData}, {fnGetDictIndex(ptRequest['request.json'],'dtparams.draw')}==1 or not {lRowCount}")
                        tSessionState = await _fnSetAdminEventsStatus(ptRequest=ptRequest
                                                           ,ptParams={'percentage':-1,'checkexists':True,'otherprogress':{"cancelinsert":True}})
                        if _fnCheckSessionState(tSessionState,'Kill',True):
                            while True:
                                print('Waiting for tempdb insert to finish, kill')
                                await fnAsyncSleep(1)
                                if not _fnCheckSessionState(self.fnGetProgress(psProgressID=ptRequest['sSessionProgressID']),'Kill',False):
                                    break

                    dtStart = time.time()
                    print(f"Starting initial temp insert")
                    await _fnSetAdminEventsStatus(ptRequest=ptRequest
                                        ,ptParams={'percentage':-1
                                            ,'status':'Starting initial temp insert'
                                            ,'errorlevel':0
                                            ,'otherprogress':{'cancelinsert':False,'insertfinished':False}}
                                        )
                    lFoundFileTable:int = await self._oKodiakShared.fnDBTemp_CreateNewTable(pbIndexIntVal=True,psDatabase=tSpecificTranslate['database_name'])
                    # return await self._oKodiakShared.fnDBTemp_CreateNewTable(pbIndexIntVal=pbIndexIntVal,pbIndexKeyVal=pbIndexKeyVal,psDatabase=psDatabase)
                    if lFoundFileTable == 0:
                        sError = "Unable to create a temp table"
                        break

                    sSQLStatement = f"""INSERT INTO [TEMPTABLENAME] (intval)
                        SELECT {tSpecificTranslate['primary_key_col']}
                        FROM {tSpecificTranslate['events_table_name']}{tSpecificTranslate['table_join']}
                        {sSQLWhere}
                        ORDER BY {sSQLOrderBy}
                        LIMIT {sSQLLimit}"""
                    # print(f"The initial {sSQLStatement}; {tSearchVars}; {lFoundFileTable}")
                    dtStart = time.time()
                    tRowCount = await self._oKodiakShared.fnDBTemp_Exec(lFoundFileTable,sSQLStatement,tSearchVars)
                    # print(tRowCount)
                    lFilteredRowCount = tRowCount['rowcount']
                    lRowCount = tRowCount['rowcount']
                    bFirstRun = True
                    await _fnSetAdminEventsStatus(ptRequest=ptRequest
                                        ,ptParams={'percentage':-1
                                            ,'status':'Initial set inserted'
                                            ,'tooltip':f"rowcount {lFilteredRowCount}"
                                            ,'errorlevel':0
                                            ,'otherprogress':{"recordsFiltered":lFilteredRowCount,"orderbyhash":hash(sSQLOrderBy)}}
                                        )
                    print(f"Time to finish {tSpecificTranslate['events_table_name']} initial pull {time.time()-dtStart}; {tRowCount}")
                    if lRowCount < tSearchVars['length']:
                        print(f"Insert is finished {lRowCount} < {tSearchVars['length']}; {bPopulatingTemp}; {bReloadTempData}")
                        bReloadTempData=None
                        bPopulatingTemp=False

                else:
                    # if bReloadTempData==False:
                    #     bFirstRun=True
                    # lRowCount = ptRequest['tSession'][f"{tSpecificTranslate['sourcetype']}-dt-rows"]
                    lFilteredRowCount = ptRequest['tSession'][f"{tSpecificTranslate['sourcetype']}-dt-filteredrows"]
                    if bPopulatingTemp:
                        # Do we already have the data required?
                        if lOrderByHash != hash(sSQLOrderBy):
                            print(f"Order by has changed, do we have to wait? {lOrderByHash} !={ hash(sSQLOrderBy)}")
                            # lRowCount=0

                        elif fnGetDictIndex(tSearchVars,'insert_start',None,lTempRowCount+1) <= lTempRowCount:
                            print(f"We have the needed rows already {tSearchVars['insert_start']} <= {lTempRowCount}")

                            # lRowCount = lTempRowCount

                        if lFilteredRowCount==0:
                            print('Waiting for tempdb insert to finish, fastrack it')
                            tSessionState = await _fnSetAdminEventsStatus(ptRequest=ptRequest
                                                        ,ptParams={'percentage':-1
                                                                   ,'checkexists':True
                                                                   ,'getprogress':True
                                                                   ,'otherprogress':{"finishinbulk":True}})
                            if not _fnCheckSessionState(tSessionState,'Fasttrack',True):
                                lFilteredRowCount = fnGetDictIndex(tSessionState, 'progress.other.recordsFiltered')
                            else:
                                while True:
                                    await fnAsyncSleep(1)
                                    tSessionState = self.fnGetProgress(psProgressID=ptRequest['sSessionProgressID'])
                                    if not _fnCheckSessionState(tSessionState,'Fasttrack',False):
                                        lFilteredRowCount = fnGetDictIndex(tSessionState, 'progress.other.recordsFiltered')
                                        break
                                    # print(f"Insert out {lRowCount}; tSessionState:{tSessionState}")

                                    print(f"Waiting for tempdb insert to finish: {tSessionState}")
                            bFirstRun = True
                            print(f"Out of loop row count {lRowCount}; bPopulatingTemp: {bPopulatingTemp}")
                        else:
                            print('NOT Waiting for tempdb insert to finish')
                    else:
                        print('NOT bPopulatingTemp, so that means that the temp impot has finished, and we can simply return data as required')

                    lFoundFileTable = ptRequest['tSession'][f"{tSpecificTranslate['sourcetype']}-dt-temptableid"]
                print(f"Before select lFoundFileTable:{lFoundFileTable}; lFilteredRowCount: {lFilteredRowCount}; lRowCount: {lRowCount}")
                sSQLStatement = f"""SELECT {tSpecificTranslate['primary_key_col']},{tSpecificTranslate['event_type_col']},DATE_FORMAT({tSpecificTranslate['event_date_col']}, '%%Y-%%m-%%d %%T'),{tSpecificTranslate['event_outcome_col']}
                        FROM {tSpecificTranslate['events_table_name']}{tSpecificTranslate['table_join']}
                        INNER JOIN [TEMPTABLENAME] ON {tSpecificTranslate['primary_key_col']} = [TEMPTABLENAME].intval
                        ORDER BY {sSQLOrderBy}
                        LIMIT {sSQLLimit}"""
                print(f"lFoundFileTable: {lFoundFileTable},sSQLStatement: {sSQLStatement},tSearchVars:{tSearchVars}")
                dtStart = time.time()
                bUnset = False
                if bPopulatingTemp:
                    bUnset = True
                    tSessionState = await _fnSetAdminEventsStatus(ptRequest=ptRequest,ptParams={
                        'percentage':-1
                        ,'status':'populating temp, wait for queue'
                        ,'checkexists':True
                        ,'getprogress':True
                        ,'otherprogress':{"clientwaiting":dtStart}})
                    if _fnCheckSessionState(tSessionState,'Pull data 1',True):
                        while True:
                            try:
                                print(f"Waiting for the temp insert to let me in {ptRequest['sSessionProgressID']}; {ptRequest['sSessionProgressID']}")
                                await fnAsyncSleep(1)
                                tSessionState = self.fnGetProgress(psProgressID=ptRequest['sSessionProgressID'])
                                if not _fnCheckSessionState(tSessionState,'Pull data 2',False):
                                    print(f"Session has been stopped/cancelled/killed")
                                    break
                                if fnGetDictIndex(tSessionState, 'progress.other.clientwaiting')!=dtStart:
                                    print(f"it's now our turn")
                                    print(f"{tSessionState}; {fnGetDictIndex(tSessionState, 'progress.other.clientwaiting')}!={dtStart}")
                                    break
                            except Exception as eError:
                                fnPrintError(f"Error waiting for a slot", eError,True)



                # await asyncio.sleep(0)
                tDataRows = await self._oKodiakShared.fnDBTemp_PullRecords(lFoundFileTable,sSQLStatement,tSearchVars)
                if bUnset:
                    await _fnSetAdminEventsStatus(ptRequest=ptRequest,ptParams={'percentage':-1
                                                                                              ,'status':'querying database, client waiting -1'
                                                                                              ,'otherprogress':{"clientwaiting":-1}})

                # await asyncio.sleep(0)
                if tDataRows == ():
                    print(f"No rows returned",lFoundFileTable,sSQLStatement,tSearchVars)
                    # So I think this means the temp table is gone
                    lFilteredRowCount=0
                else:
                    print(f"Found data len(tDataRows): {len(tDataRows)}")
                    # tTest = await self._oKodiakShared.fnDBTemp_PullRecords(lFoundFileTable,"SELECT * FROM [TEMPTABLENAME] LIMIT 2",tSearchVars)
                    # print(f"temptable: {tTest}")
                    # raise Exception("Error pulling records")
                print(f"Time to finish {tSpecificTranslate['events_table_name']} pull {time.time()-dtStart}; bPopulatingTemp: {bPopulatingTemp}")
                tDataReturn = {"data":tDataRows
                      }

                if tSpecificTranslate['user_savedsearch_prefname']:
                    tUserPrefs = await self.fnReadUserAttributes(ptRequest['sSessionProgressID'],ptRequest['tSession']['userid'],f"prefs.{tSpecificTranslate['user_savedsearch_prefname']}.last.autoload")
                    # print(tUserPrefs)
                    # print(ptRequest['request.json']['searchparams'])
                    # Save search params to user
                    if fnGetDictIndex(tUserPrefs,'data'):
                        print(f"Set last search to {ptRequest['request.json']['searchparams']}")
                        # await fnAsyncSleep(1.5)
                        await self.fnUpdateUserAttributes(ptRequest['sSessionProgressID'],ptRequest['tSession']['userid'],f"state.{tSpecificTranslate['user_savedsearch_prefname']}.last.params",ptRequest['request.json']['searchparams'])
                        # tDataReturn = {"data":True,"pushmessage":{'eventname':'vivo.servfnDiskUsageObjecticesetting','data':tKeyset}}
                        tPushMessage = {'eventname':'sputnik.usersettingschanged','data':{'detail':{'userattributekey':f"state.{tSpecificTranslate['user_savedsearch_prefname']}.last.params",'newvalue':ptRequest['request.json']['searchparams'],'userid':'1'}}}
                if fnIfDictHasIndex(ptRequest['request.json'], 'dtparams'):
                    tDataReturn['draw'] = ptRequest['request.json']['dtparams']['draw']
                    tDataReturn["recordsTotal"]=lRowCount
                    tDataReturn["recordsFiltered"]=lFilteredRowCount
                if bFirstRun:
                    tCookieFunctions=[{'fn':"set","name":f"{tSpecificTranslate['sourcetype']}-dt-rows","value":lRowCount}
                        ,{'fn':"set","name":f"{tSpecificTranslate['sourcetype']}-dt-filteredrows","value":lFilteredRowCount}
                        ,{'fn':"set","name":f"{tSpecificTranslate['sourcetype']}-dt-temptableid","value":lFoundFileTable}
                        ,{'fn':"set","name":f"{tSpecificTranslate['sourcetype']}-dt-filterhash","value":sSearchHash}]
                    print(f"Setting cookies to : {tCookieFunctions}")


            except Exception as eError:
                sError = fnPrintError("Failed fnPullAdminEvents",eError,True)

            break
        if sError:
            await _fnSetAdminEventsStatus(ptRequest=ptRequest,ptParams={'percentage':100,'status':'Failed to pull data','errorlevel':1})
            bReloadTempData=None
            tDataReturn = {}
            bOutcome=False
        else:
            bOutcome=True
        # await asyncio.sleep(0)
        # print(f"Exiting fnPullAdminEvents {bPopulatingTemp}")
        if bReloadTempData==True or bReloadTempData==False:
            print(f"fnPullAdminEvents - Exiting sending the async off")
            await _fnSetAdminEventsStatus(ptRequest=ptRequest,ptParams={'percentage':-1,'status':'populating table data','errorlevel':0})
            tReturn = self.fnReturnClientSideCommands(tDataReturn,tPushMessage,tCookieFunctions)
            # tReturn = tDataReturn
            # print(f"Send it out there {bReloadTempData}")
            oTask = asyncio.create_task(_fnPullEventIDsToTempDB(lFoundFileTable,bReloadTempData,ptRequest['sSessionProgressID'],tSpecificTranslate))
        else:
            if bPopulatingTemp:
                print(f"fnPullAdminEvents - Exiting but temp still populating")
                await _fnSetAdminEventsStatus(ptRequest=ptRequest,ptParams={'percentage':-1,'status':'returning data','errorlevel':0})
            else:
                print(f"fnPullAdminEvents - Exiting with final state 100")
                # print(tDataReturn)
                await _fnSetAdminEventsStatus(ptRequest=ptRequest,ptParams={'percentage':100,'status':'returning data','errorlevel':0})
            tReturn = self.fnFinalState(ptRequest['sSessionProgressID'],tDataReturn,bOutcome,sError,tPushMessage,tCookieFunctions)
        # print(f"Leaving PullAdminE {tReturn}")
        return tReturn

