import subprocess,time,os,sys,datetime as dt
d=dt.date(2022,1,3);end=dt.date(2026,10,16);t0=time.time()
while d<=end:
    if d.weekday()<5:
        s=d.strftime('%Y%m%d');f=f'raw/{s}.txt'
        if not os.path.exists(f):
            r=subprocess.run(['curl','-s','-m','30','-o',f,'-w','%{http_code}',f'https://cdn.finra.org/equity/regsho/daily/CNMSshvol{s}.txt'],capture_output=True,text=True).stdout
            if r!='200': 
                os.remove(f) if os.path.exists(f) else None
                open(f'raw/{s}.miss','w').write(r)
            time.sleep(0.3)
            if time.time()-t0>540: print('partial',s);sys.exit()
    d+=dt.timedelta(1)
print('done')
