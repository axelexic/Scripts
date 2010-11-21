#!/usr/bin/env python

import subprocess;
import operator;
import os
import os.path as path;
import shutil;
import sys;
import time;

MAX_BACKUPS=8 # Two months worth.

BACKUPDIR="/Users/swami/Workspace/vm"
VMDIRS="/Volumes/Storage/vm"
VMWARE_INSTALL_DIR="/Library/Application Support/VMware Fusion"

EXCLUDE_FILE_NAME=".excludes"

RSYNC="/Users/swami/Workspace/MacPorts/bin/rsync"
RSYNC_FLAGS=["--archive", "--hard-links", "--sparse", "--verbose", "--stats", "--fileflags"]


VMRUN=VMWARE_INSTALL_DIR+"/vmrun"


def list_vm():
    program_args=[ VMRUN, "-t", "Fusion", "list" ];
    vmrun=subprocess.Popen(program_args, stdout=subprocess.PIPE);
    results=vmrun.communicate()[0];
    return results.split("\n")[1:-1]

def stop_vm(vmname):
    print "Stopping VM: %s"%vmname;
    program_args=[VMRUN, "-t", "Fusion", "stop", vmname ]
    vmrun=subprocess.Popen(program_args);
    vmrun.wait();
    
def start_vm(vmname):
    print "Starting VM: %s"%vmname;
    program_args=[VMRUN, "-t", "Fusion", "start", vmname ]
    vmrun=subprocess.Popen(program_args, stdout=subprocess.PIPE);
    vmrun.wait();

def suspend_vm(vmname):
    print "Suspending VM: %s"%vmname;
    program_args=[VMRUN, "-t", "Fusion", "suspend", vmname ]
    vmrun=subprocess.Popen(program_args, stdout=subprocess.PIPE);
    vmrun.wait();


def execute_rsync(rsync_flags, backup_root):

    program_args=[RSYNC];
    program_args.extend(rsync_flags);
    
    excluded_files = "%s/%s"%(backup_root,EXCLUDE_FILE_NAME);
        
    if os.access(excluded_files, os.R_OK):
        program_args.append('--exclude-from=%s'%(excluded_files));

    destination_log= "%s/rsync.log"%backup_root;
    destination_err= "%s/rsync-err.log"%backup_root;
    
    stdout_file=open(destination_log, "w", 0);
    stderr_file=open(destination_err, "w", 0);

    message="Backup Started at '%s' with command line:\n"%(time.strftime("%Y-%m-%d %H:%M:%S"));

    stdout_file.write("-*-\n");
    stdout_file.write(message);
    stdout_file.write(program_args.__str__());
    stdout_file.write("\n--\n\n");

    stderr_file.write("-*-\n");
    stderr_file.write(message);
    stderr_file.write(program_args.__str__( ));
    stderr_file.write("\n--\n\n");

    rsync=subprocess.Popen(program_args, stdout=stdout_file, stderr=stderr_file);
    rsync.wait();


def backup_process(vmname):
    
    try:
        backup_dir_name=path.basename(vmname.split('.vmwarevm', 1)[0]);
    except Exception, e:
        print "Error processing the vmware file name. Error: ", e.args[0];
        return
    
    backup_root=BACKUPDIR+'/'+backup_dir_name;
    backup_dir_old_names=os.listdir(backup_root);

    backup_dir_dict=dict();
    
    for dir in backup_dir_old_names:
        dir_path=backup_root+'/'+dir;
        try:
            if path.isdir(dir_path):
                new_dir_name=int(dir) + 1;
                backup_dir_dict[dir_path]=new_dir_name;
            else:
                pass;
        except ValueError, ve:
            pass;
        except Exception, e:
            raise e;


    backup_dir_sorted=sorted(backup_dir_dict.iteritems(), key=operator.itemgetter(1), reverse=True);
    
    rsync_flags=list();
    rsync_flags.extend(RSYNC_FLAGS);
    
    for old,new in backup_dir_sorted:
        new_dir="%s/%.2d"%(backup_root,new);
        try:
            if not '--dry-run' in rsync_flags:
                os.rename(old, new_dir);
            # Here we append link dest paths.
            rsync_flags.append('--link-dest=../%0.2d/'%(new))
        except Exception, e:
            print "Renaming failed. Error: %s"%(e.args[0]);
            raise e;
    
    source=vmname.rstrip('/')+'/'; # rsync needs a single trailing slash
    destination="%s/%.2d"%(backup_root,0);
    rsync_flags.append(source);
    rsync_flags.append(destination);
    
    # Now run rsync
    execute_rsync(rsync_flags, backup_root);
        
    try:
        if len(backup_dir_sorted) > MAX_BACKUPS:
            (blan,oldest)=backup_dir_sorted[0];
            oldest_file="%s/%.2d"%(backup_root,oldest);
            print "Deleting: %s"%(oldest_file);
            if not '--dry-run' in rsync_flags:
                shutil.rmtree(oldest_file)
        
    except IndexError, ie:
        print backup_dir_sorted;
    


if __name__=='__main__':

    is_dry_run=False;
    if '--dry-run' in sys.argv:
        RSYNC_FLAGS.append('--dry-run');
        is_dry_run=True;

    # Before doing anything, check to see if we have read permission on
    # vmdirs and write permission on the backup dir.
    if not os.access(BACKUPDIR, os.R_OK|os.W_OK|os.X_OK):
        print "You do not read/write/execute permission for backup dir: %s"%BACKUPDIR;
        sys.exit(-1);
        
    if not os.access(VMDIRS, os.R_OK):
        print "You do not read permission for VMDIRS dir: %s"%VMDIRS;
        sys.exit(-2);
    
    if not is_dry_run:
        running_vm=list_vm();
    # First suspend all the running VMs.
        for vm in running_vm:
            suspend_vm(vm);
    
    # Backup the entire set of VMs, running or not.
    VMS=[VMDIRS+'/'+x for x in os.listdir(VMDIRS) if x.endswith(".vmwarevm")];
    
    for vm in VMS:
        print "Backing up vm: ",vm;
        backup_process(vm);
        
    # Restart the old previously running VMs
    if not is_dry_run:
        for vm in running_vm:
            start_vm(vm);
        
    # And we are done!