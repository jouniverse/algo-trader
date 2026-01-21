"kdb+tick 2.8 2014.03.12"

/q tick.q SRC [DST] [-p 5010] [-o h]
system"l tick/",(src:first .z.x,enlist"sym"),".q"

if[not system"p";system"p 5010"]

\l tick/u.q
\d .u
ld:{[dt]
    if[not type key L::`$(-10_string L),string dt;
    /Amend entire - create empty logfile for the new day
        .[L;();:;()];
    ];
    /Replay the logfile
    i::j::-11!(-2;L);
    /Check if the logfile is corrupt
    if[0<=type i;-2 (string L)," is a corrupt log. Truncate to length ",(string last i)," and restart";
        exit 1
    ];
    hopen L
    };

tick:{[src;tplog]
    init[];
    if[not min(`time`sym~2#key flip value@)each t;'`timesym];
    @[;`sym;`g#]each t;
    d::.z.D;
    / create handle to tplog file if it exists
    if[l::count tplog;
        L::`$":",tplog,"/",src,10#".";
        l::ld d
    ]
    };

/ call .u.end, increment u.d., create new logfile for the next day if it exists
endofday:{end d;d+:1;if[l;hclose l;l::ld d]};
ts:{[dt]
    if[d<dt;
        if[d<dt-1;system"t 0";'"more than one day?"];
        endofday[]
    ]
    };

/ batching mode
if[system"t";
 .z.ts:{pub'[t;value each t];@[`.;t;@[;`sym;`g#]0#];i::j;ts .z.D};
 upd:{[tab;data]
  if[not -16=type first first data;
   if[d<"d"$a:.z.P;.z.ts[]];a:"n"$a;data:$[0>type first data;a,data;(enlist(count first data)#a),data]];
  tab insert data;if[l;l enlist(`upd;tab;data);j+:1]}];

/ zero latency
if[not system"t";
 .z.ts:{ts .z.D};
 upd:{[tab;data]
  ts"d"$a:.z.P;
  if[not -16=type first first data;a:"n"$a;data:$[0>type first data;a,data;(enlist(count first data)#a),data]];
  f:key flip value tab;pub[tab;$[0>type first data;enlist f!data;flip f!data]];if[l;l enlist(`upd;tab;data);i+:1]}];

\d .
.u.tick[src;.z.x 1];

\
 globals used
 .u.w - dictionary of tables->(handle;syms)
 .u.i - msg count in log file
 .u.j - total msg count (log file plus those held in buffer)
 .u.t - table names
 .u.L - tp log filename, e.g. `:./sym2008.09.11
 .u.l - handle to tp log file
 .u.d - date

/test
>q tick.q
>q tick/ssl.q

/run
>q tick.q sym  .  -p 5010	/tick
>q tick/r.q :5010 -p 5011	/rdb
>q sym            -p 5012	/hdb
>q tick/ssl.q sym :5010		/feed
