import os
import sys
###
from collections import defaultdict
###
# from prettyplotlib import plt
###
import boto
conn = boto.connect_s3(anon=True)

# Since April 2016, the public dataset bucket is s3://commoncrawl 
# (migrated from s3://aws-publicdatasets/common-crawl)
pds = conn.get_bucket('commoncrawl')

# CC-MAIN-2016-07
target = str(sys.argv[1])

sys.stdout.write('Processing {}\n'.format(target))

# Get all segments
segments = list(pds.list('crawl-data/{}/segments/'.format(target), delimiter='/'))
# Record the total size and all file paths for the segments
files = dict(warc=[], wet=[], wat=[], segment=[x.name for x in segments])
size = dict(warc=[], wet=[], wat=[])

# Traverse each segment and all the files they contain
for i, segment in enumerate(segments):
  sys.stderr.write('\rProcessing segment {} of {}'.format(i, len(segments)))
  for ftype in ['warc', 'wat', 'wet']:
    for f in pds.list(segment.name + ftype + '/'):
      files[ftype].append(f.name)
      size[ftype].append(f.size)
sys.stderr.write('\n')

# Write total size and file paths to files
prefix = 'crawl_stats/{}/'.format(target)
if not os.path.exists(prefix):
  os.makedirs(prefix)
###
f = open(prefix + 'crawl.size', 'w')
for ftype, val in size.items():
  f.write('{}\t{}\t{}\n'.format(ftype, sum(val), len(val)))
f.close()
###
for ftype in files:
  f = open(prefix + '{}.paths'.format(ftype), 'w')
  for fn in files[ftype]:
    f.write(fn + '\n')
  f.close()
###
# Kid friendly stats (i.e. console)
for ftype, fsize in size.items():
  sys.stderr.write('{} files contain {} bytes over {} files\n'.format(ftype.upper(), sum(fsize), len(files[ftype])))
###
# To upload to the correct spot on S3
# gzip *.paths
# s3cmd put --acl-public *.paths.gz s3://commoncrawl/crawl-data/CC-MAIN-YYYY-WW/

###
# Plot
#for ftype, fsize in size.items():
#  if not fsize:
#    continue
#  plt.hist(fsize, bins=50)
#  plt.xlabel('Size (bytes)')
#  plt.ylabel('Count')
#  plt.title('Distribution for {}'.format(ftype.upper()))
#  plt.savefig(prefix + '{}_dist.pdf'.format(ftype))
#  #plt.show(block=True)
#  plt.close()
###

# Find missing WAT / WET files
warc = set([x.strip() for x in open(prefix + 'warc.paths').readlines()])
wat = [x.strip() for x in open(prefix + 'wat.paths').readlines()]
wat = set([x.replace('.warc.wat.', '.warc.').replace('/wat/', '/warc/') for x in wat])
wet = [x.strip() for x in open(prefix + 'wet.paths').readlines()]
wet = set([x.replace('.warc.wet.', '.warc.').replace('/wet/', '/warc/') for x in wet])
# Work out the missing files and segments
missing = sorted(warc - wat)
missing_segments = defaultdict(list)
missing_files = 0
for fn in missing:
  start, suffix = fn.split('/warc/')
  segment = start.split('/')[-1]
  missing_segments[segment].append(fn)
  missing_files += 1
missing = sorted(warc - wet)
for fn in missing:
  start, suffix = fn.split('/warc/')
  segment = start.split('/')[-1]
  if fn not in missing_segments[segment]:
    missing_files += 1
    print(">>", segment, fn)
    missing_segments[segment].append(fn)
# Save the files such that we can run a new WEATGenerator job
prefix += 'weat.queued/'
if not os.path.exists(prefix):
  os.mkdir(prefix)
sys.stderr.write('Total of {} missing/incomplete segments with {} missing parts\n'.format(len(missing_segments), missing_files))
for seg, files in missing_segments.iteritems():
  sys.stderr.write('{} has {} missing parts\n'.format(seg, len(files)))
  f = open(prefix + 'seg_{}'.format(seg), 'w')
  [f.write('s3a://commoncrawl/{}\n'.format(fn)) for fn in files]
  f.close()
