# -*- mode: ruby -*-
# vi: set ft=ruby :


# Env variable TZ is optional
timezone = ENV["TZ"]


Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/focal64"
  config.vm.hostname = "beehive"
  
  config.vm.network "private_network", type: "dhcp"


  config.vm.provider "virtualbox" do |vb|
    vb.memory = "2048"
  end


  config.vm.provision "ansible" do |ansible|

    
    ansible.compatibility_mode = "2.0"
    ansible.playbook = "playbook.yml"
    ansible.extra_vars = {
      node_id: "test-beekeeper" , 
      beekeeper_registration_host: "10.0.2.2" ,  # used in /etc/waggle/config.ini
      beekeeper_registration_port: "20022" ,  # used in /etc/waggle/config.ini
      timezone: timezone   
    }
  end

   
end
