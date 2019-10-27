import os
import site

class PathFile:

    file_path = None
    
    def check(self):
        file_path = self.get_file_path()
        exists = os.path.exists(file_path)
        if exists:
            print('Path file exists at {}.'.format(file_path))
            with open(file_path) as f:
                content = f.read()
            print('Contents:\n  {}'.format(content))
        else:
            print("The path file doesn't exist yet.")
            print('Suggested location: {}'.format(file_path))
            print('Suggested content: {}'.format(self.get_src()))
        return exists

    def create(self, overwrite=False):
        file_path = self.get_file_path()
        if os.path.exists(file_path):
            print('Path file exists ({})'.format(file_path))
            if overwrite:
                print('Overwriting.')
            else:
                print('Leaving existing path file in place.')
                return file_path
        src = self.get_src()
        print('Writing "{}" to {}.'.format(src, file_path))
        with open(file_path, 'w') as f:
            f.write(src)

    def get_file_path(self):
        if not self.file_path:
            site_packages = site.getusersitepackages()
            self.file_path = os.path.join(site_packages, 'gssurgo.pth')
        return self.file_path
    
    def get_src(self):
        project_root = os.path.dirname(os.path.dirname(__file__))
        return os.path.join(project_root, 'src')

if __name__ == '__main__':
    pf = PathFile()
    pf.create()
