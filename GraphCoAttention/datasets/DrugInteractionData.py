import os
import torch
import wget
import numpy as np
import pandas as pd
from tqdm import tqdm
from abc import ABC, ABCMeta

from ogb.utils.url import decide_download, download_url, extract_zip
import ogb.utils.mol as mol
import torch_geometric as tg

from GraphCoAttention.data.MultipartiteData import BipartitePairData


class DrugDrugInteractionData(tg.data.InMemoryDataset, ABC):
    def __init__(self, root):
        self.url = 'http://snap.stanford.edu/decagon/bio-decagon-combo.tar.gz'
        self.original_root = root
        super(DrugDrugInteractionData, self).__init__(root=root)
        self.data, self.slices = torch.load(self.processed_paths[0])

    @property
    def raw_file_names(self):
        return 'bio-decagon-combo.tar.gz'

    @property
    def processed_file_names(self):
        return 'decagon.pt'

    def download(self):
        if decide_download(self.url):
            wget.download(self.url, self.raw_paths[0])
        else:
            print('Stop download.')
            exit(-1)

    @staticmethod
    def mol2pyg(molecule):
        graph = mol.smiles2graph(molecule)
        data = tg.data.Data()
        data.__num_nodes__ = int(graph['num_nodes'])
        data.edge_index = torch.from_numpy(graph['edge_index']).to(torch.int64)
        data.edge_attr = torch.from_numpy(graph['edge_feat']).to(torch.int64)
        data.x = torch.from_numpy(graph['node_feat']).to(torch.int64)
        return data

    def process(self):
        import pubchempy as pcp

        df = pd.read_csv(self.raw_paths[0], compression='gzip', header=0, encoding="ISO-8859-1", error_bad_lines=False)
        records = df.to_records(index=False)
        raw_tuple = list(records)[:1000]

        data_list = []
        for cid_i, cid_j, label, name in tqdm(raw_tuple):
            mol_i = pcp.Compound.from_cid(int(cid_i.strip('CID'))).isomeric_smiles
            mol_j = pcp.Compound.from_cid(int(cid_j.strip('CID'))).isomeric_smiles

            data_i, data_j = self.mol2pyg(mol_i), self.mol2pyg(mol_j)

            data = BipartitePairData(x_i=data_i.x, x_j=data_j.x,
                                     inner_edge_index_i=data_i.edge_index,
                                     inner_edge_index_j=data_j.edge_index)

            data.y = torch.tensor([int(label.strip('C'))], dtype=torch.long)


        data, slices = self.collate(data_list)
        print('Saving...')
        torch.save((data, slices), self.processed_paths[0])


if __name__ == '__main__':
    dataset = DrugDrugInteractionData(root=os.path.join('GraphCoAttention', 'data'))